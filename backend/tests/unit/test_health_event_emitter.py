"""Unit tests for health event emitter service.

Tests the HealthEventEmitter service which tracks system health state
and emits WebSocket events when health status transitions occur.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.health_event_emitter import (
    ComponentHealthState,
    ErrorSeverity,
    HealthEventEmitter,
    HealthStatus,
    emit_system_error,
    get_health_event_emitter,
    reset_health_event_emitter,
)


@pytest.fixture
def health_emitter() -> HealthEventEmitter:
    """Create a fresh health emitter for testing."""
    return HealthEventEmitter()


@pytest.fixture
def mock_ws_emitter() -> MagicMock:
    """Create a mock WebSocket emitter."""
    mock = MagicMock()
    mock.emit = AsyncMock(return_value=True)
    return mock


@pytest.fixture(autouse=True)
def reset_singleton() -> None:
    """Reset the global singleton before each test."""
    reset_health_event_emitter()


class TestHealthStatus:
    """Tests for HealthStatus enum."""

    def test_health_status_values(self) -> None:
        """Test that all expected status values exist."""
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"
        assert HealthStatus.UNKNOWN.value == "unknown"


class TestErrorSeverity:
    """Tests for ErrorSeverity enum."""

    def test_error_severity_values(self) -> None:
        """Test that all expected severity values exist."""
        assert ErrorSeverity.LOW.value == "low"
        assert ErrorSeverity.MEDIUM.value == "medium"
        assert ErrorSeverity.HIGH.value == "high"
        assert ErrorSeverity.CRITICAL.value == "critical"


class TestComponentHealthState:
    """Tests for ComponentHealthState dataclass."""

    def test_default_state(self) -> None:
        """Test default component health state."""
        state = ComponentHealthState()
        assert state.status == HealthStatus.UNKNOWN
        assert isinstance(state.last_changed, datetime)
        assert state.details == {}

    def test_custom_state(self) -> None:
        """Test component health state with custom values."""
        now = datetime.now(UTC)
        details = {"pool_size": 10}
        state = ComponentHealthState(
            status=HealthStatus.HEALTHY,
            last_changed=now,
            details=details,
        )
        assert state.status == HealthStatus.HEALTHY
        assert state.last_changed == now
        assert state.details == details


class TestHealthEventEmitter:
    """Tests for HealthEventEmitter class."""

    def test_initialization(self, health_emitter: HealthEventEmitter) -> None:
        """Test emitter initializes with empty state."""
        assert health_emitter._component_states == {}
        assert health_emitter._overall_status == HealthStatus.UNKNOWN
        assert health_emitter._emitter is None

    def test_set_emitter(
        self, health_emitter: HealthEventEmitter, mock_ws_emitter: MagicMock
    ) -> None:
        """Test setting the WebSocket emitter."""
        health_emitter.set_emitter(mock_ws_emitter)
        assert health_emitter._emitter == mock_ws_emitter

    def test_get_component_status_unknown(self, health_emitter: HealthEventEmitter) -> None:
        """Test getting status for unknown component returns UNKNOWN."""
        assert health_emitter.get_component_status("nonexistent") == HealthStatus.UNKNOWN

    def test_get_all_component_statuses_empty(self, health_emitter: HealthEventEmitter) -> None:
        """Test getting all statuses when no components tracked."""
        assert health_emitter.get_all_component_statuses() == {}

    def test_get_overall_status_initial(self, health_emitter: HealthEventEmitter) -> None:
        """Test overall status starts as UNKNOWN."""
        assert health_emitter.get_overall_status() == HealthStatus.UNKNOWN

    @pytest.mark.asyncio
    async def test_check_and_emit_first_status(
        self, health_emitter: HealthEventEmitter, mock_ws_emitter: MagicMock
    ) -> None:
        """Test first status check emits event (UNKNOWN -> healthy)."""
        health_emitter.set_emitter(mock_ws_emitter)

        changed = await health_emitter.check_and_emit(
            component="database",
            new_status="healthy",
            details={"pool_size": 10},
        )

        assert changed is True
        assert health_emitter.get_component_status("database") == HealthStatus.HEALTHY
        mock_ws_emitter.emit.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_and_emit_no_change(
        self, health_emitter: HealthEventEmitter, mock_ws_emitter: MagicMock
    ) -> None:
        """Test that same status does not emit event."""
        health_emitter.set_emitter(mock_ws_emitter)

        # First call - should emit
        await health_emitter.check_and_emit("database", "healthy")
        assert mock_ws_emitter.emit.call_count == 1

        # Second call with same status - should not emit
        changed = await health_emitter.check_and_emit("database", "healthy")
        assert changed is False
        assert mock_ws_emitter.emit.call_count == 1

    @pytest.mark.asyncio
    async def test_check_and_emit_status_transition(
        self, health_emitter: HealthEventEmitter, mock_ws_emitter: MagicMock
    ) -> None:
        """Test status transition emits event."""
        health_emitter.set_emitter(mock_ws_emitter)

        # First: healthy
        await health_emitter.check_and_emit("database", "healthy")
        assert mock_ws_emitter.emit.call_count == 1

        # Second: transition to unhealthy
        changed = await health_emitter.check_and_emit("database", "unhealthy")
        assert changed is True
        assert mock_ws_emitter.emit.call_count == 2
        assert health_emitter.get_component_status("database") == HealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_check_and_emit_updates_details_without_emit(
        self, health_emitter: HealthEventEmitter, mock_ws_emitter: MagicMock
    ) -> None:
        """Test details are updated even when status doesn't change."""
        health_emitter.set_emitter(mock_ws_emitter)

        # First call with details
        await health_emitter.check_and_emit("database", "healthy", {"version": "14.0"})

        # Second call with different details but same status
        await health_emitter.check_and_emit("database", "healthy", {"version": "14.1"})

        # Details should be updated
        state = health_emitter._component_states["database"]
        assert state.details == {"version": "14.1"}

    @pytest.mark.asyncio
    async def test_check_and_emit_invalid_status_defaults_to_unknown(
        self, health_emitter: HealthEventEmitter, mock_ws_emitter: MagicMock
    ) -> None:
        """Test invalid status string defaults to UNKNOWN."""
        health_emitter.set_emitter(mock_ws_emitter)

        await health_emitter.check_and_emit("database", "invalid_status")

        assert health_emitter.get_component_status("database") == HealthStatus.UNKNOWN

    @pytest.mark.asyncio
    async def test_check_and_emit_enum_status(
        self, health_emitter: HealthEventEmitter, mock_ws_emitter: MagicMock
    ) -> None:
        """Test using HealthStatus enum directly."""
        health_emitter.set_emitter(mock_ws_emitter)

        changed = await health_emitter.check_and_emit("database", HealthStatus.DEGRADED)

        assert changed is True
        assert health_emitter.get_component_status("database") == HealthStatus.DEGRADED

    @pytest.mark.asyncio
    async def test_check_and_emit_no_emitter_configured(
        self, health_emitter: HealthEventEmitter
    ) -> None:
        """Test emission without configured emitter doesn't raise."""
        # Should not raise, just log
        changed = await health_emitter.check_and_emit("database", "healthy")
        assert changed is True
        assert health_emitter.get_component_status("database") == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_update_all_components(
        self, health_emitter: HealthEventEmitter, mock_ws_emitter: MagicMock
    ) -> None:
        """Test updating multiple components at once."""
        health_emitter.set_emitter(mock_ws_emitter)

        changed = await health_emitter.update_all_components(
            statuses={
                "database": "healthy",
                "redis": "healthy",
                "ai_service": "degraded",
            },
            details={
                "database": {"pool_size": 10},
                "redis": {"version": "7.0"},
            },
        )

        # All components should have changed (from UNKNOWN)
        assert set(changed) == {"database", "redis", "ai_service"}
        assert health_emitter.get_component_status("database") == HealthStatus.HEALTHY
        assert health_emitter.get_component_status("redis") == HealthStatus.HEALTHY
        assert health_emitter.get_component_status("ai_service") == HealthStatus.DEGRADED

    @pytest.mark.asyncio
    async def test_update_all_components_partial_change(
        self, health_emitter: HealthEventEmitter, mock_ws_emitter: MagicMock
    ) -> None:
        """Test update_all_components only reports actual changes."""
        health_emitter.set_emitter(mock_ws_emitter)

        # First update
        await health_emitter.update_all_components(
            statuses={"database": "healthy", "redis": "healthy"}
        )

        # Second update - only redis changes
        changed = await health_emitter.update_all_components(
            statuses={"database": "healthy", "redis": "unhealthy"}
        )

        assert changed == ["redis"]


class TestOverallStatusCalculation:
    """Tests for overall system health calculation."""

    @pytest.mark.asyncio
    async def test_overall_healthy_when_all_healthy(
        self, health_emitter: HealthEventEmitter, mock_ws_emitter: MagicMock
    ) -> None:
        """Test overall status is healthy when all components healthy."""
        health_emitter.set_emitter(mock_ws_emitter)

        await health_emitter.update_all_components(
            statuses={
                "database": "healthy",
                "redis": "healthy",
                "ai_service": "healthy",
            }
        )

        assert health_emitter.get_overall_status() == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_overall_unhealthy_when_critical_down(
        self, health_emitter: HealthEventEmitter, mock_ws_emitter: MagicMock
    ) -> None:
        """Test overall status is unhealthy when critical component down."""
        health_emitter.set_emitter(mock_ws_emitter)

        # Database is critical
        await health_emitter.update_all_components(
            statuses={
                "database": "unhealthy",
                "redis": "healthy",
                "ai_service": "healthy",
            }
        )

        assert health_emitter.get_overall_status() == HealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_overall_unhealthy_when_redis_down(
        self, health_emitter: HealthEventEmitter, mock_ws_emitter: MagicMock
    ) -> None:
        """Test overall status is unhealthy when Redis (critical) is down."""
        health_emitter.set_emitter(mock_ws_emitter)

        await health_emitter.update_all_components(
            statuses={
                "database": "healthy",
                "redis": "unhealthy",
                "ai_service": "healthy",
            }
        )

        assert health_emitter.get_overall_status() == HealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_overall_degraded_when_non_critical_down(
        self, health_emitter: HealthEventEmitter, mock_ws_emitter: MagicMock
    ) -> None:
        """Test overall status is degraded when non-critical component down."""
        health_emitter.set_emitter(mock_ws_emitter)

        await health_emitter.update_all_components(
            statuses={
                "database": "healthy",
                "redis": "healthy",
                "ai_service": "unhealthy",  # Not in critical list
            }
        )

        assert health_emitter.get_overall_status() == HealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_overall_degraded_when_component_degraded(
        self, health_emitter: HealthEventEmitter, mock_ws_emitter: MagicMock
    ) -> None:
        """Test overall status is degraded when any component is degraded."""
        health_emitter.set_emitter(mock_ws_emitter)

        await health_emitter.update_all_components(
            statuses={
                "database": "healthy",
                "redis": "healthy",
                "ai_service": "degraded",
            }
        )

        assert health_emitter.get_overall_status() == HealthStatus.DEGRADED


class TestSystemErrorEmission:
    """Tests for system error event emission."""

    @pytest.mark.asyncio
    async def test_emit_system_error(
        self, health_emitter: HealthEventEmitter, mock_ws_emitter: MagicMock
    ) -> None:
        """Test emitting system error event."""
        health_emitter.set_emitter(mock_ws_emitter)

        result = await health_emitter.emit_system_error(
            error_code="AI_SERVICE_CRASH",
            message="Nemotron service crashed unexpectedly",
            severity=ErrorSeverity.HIGH,
            details={"exit_code": 137},
            recoverable=True,
        )

        assert result is True
        mock_ws_emitter.emit.assert_called_once()

        # Verify payload structure
        call_args = mock_ws_emitter.emit.call_args
        payload = call_args[0][1]  # Second positional arg
        assert payload["error"] == "AI_SERVICE_CRASH"
        assert payload["message"] == "Nemotron service crashed unexpectedly"
        assert payload["details"] == {"exit_code": 137}
        assert payload["recoverable"] is True

    @pytest.mark.asyncio
    async def test_emit_system_error_no_emitter(self, health_emitter: HealthEventEmitter) -> None:
        """Test system error emission without emitter returns False."""
        result = await health_emitter.emit_system_error(
            error_code="TEST_ERROR",
            message="Test error message",
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_emit_system_error_string_severity(
        self, health_emitter: HealthEventEmitter, mock_ws_emitter: MagicMock
    ) -> None:
        """Test emit_system_error accepts string severity."""
        health_emitter.set_emitter(mock_ws_emitter)

        result = await health_emitter.emit_system_error(
            error_code="TEST_ERROR",
            message="Test message",
            severity="critical",  # String instead of enum
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_emit_system_error_invalid_severity_defaults(
        self, health_emitter: HealthEventEmitter, mock_ws_emitter: MagicMock
    ) -> None:
        """Test invalid severity defaults to MEDIUM."""
        health_emitter.set_emitter(mock_ws_emitter)

        result = await health_emitter.emit_system_error(
            error_code="TEST_ERROR",
            message="Test message",
            severity="invalid",  # type: ignore[arg-type]
        )

        assert result is True
        # Should not raise, severity is normalized internally


class TestReset:
    """Tests for emitter reset functionality."""

    @pytest.mark.asyncio
    async def test_reset_clears_state(
        self, health_emitter: HealthEventEmitter, mock_ws_emitter: MagicMock
    ) -> None:
        """Test reset clears all tracked state."""
        health_emitter.set_emitter(mock_ws_emitter)

        # Add some state
        await health_emitter.check_and_emit("database", "healthy")
        await health_emitter.check_and_emit("redis", "healthy")

        # Reset
        health_emitter.reset()

        # State should be cleared
        assert health_emitter._component_states == {}
        assert health_emitter._overall_status == HealthStatus.UNKNOWN


class TestGlobalSingleton:
    """Tests for global singleton pattern."""

    def test_get_health_event_emitter_returns_same_instance(self) -> None:
        """Test get_health_event_emitter returns singleton."""
        emitter1 = get_health_event_emitter()
        emitter2 = get_health_event_emitter()

        assert emitter1 is emitter2

    def test_reset_clears_singleton(self) -> None:
        """Test reset_health_event_emitter clears singleton."""
        emitter1 = get_health_event_emitter()
        reset_health_event_emitter()
        emitter2 = get_health_event_emitter()

        assert emitter1 is not emitter2


class TestModuleLevelFunctions:
    """Tests for module-level convenience functions."""

    @pytest.mark.asyncio
    async def test_emit_system_error_function(self) -> None:
        """Test module-level emit_system_error function."""
        # Should not raise even without emitter configured
        result = await emit_system_error(
            error_code="TEST_ERROR",
            message="Test message",
        )

        # Returns False because no emitter is configured
        assert result is False

    @pytest.mark.asyncio
    async def test_emit_system_error_function_with_emitter(self) -> None:
        """Test emit_system_error with configured emitter."""
        mock_emitter = MagicMock()
        mock_emitter.emit = AsyncMock(return_value=True)

        emitter = get_health_event_emitter()
        emitter.set_emitter(mock_emitter)

        result = await emit_system_error(
            error_code="TEST_ERROR",
            message="Test message",
            severity=ErrorSeverity.HIGH,
            details={"key": "value"},
            recoverable=False,
        )

        assert result is True
        mock_emitter.emit.assert_called_once()


class TestEventPayloadStructure:
    """Tests for WebSocket event payload structure."""

    @pytest.mark.asyncio
    async def test_health_changed_payload_structure(
        self, health_emitter: HealthEventEmitter, mock_ws_emitter: MagicMock
    ) -> None:
        """Test health changed event has correct payload structure."""
        from backend.core.websocket.event_types import WebSocketEventType

        health_emitter.set_emitter(mock_ws_emitter)

        await health_emitter.check_and_emit("database", "healthy")

        # Verify emit was called with correct event type
        call_args = mock_ws_emitter.emit.call_args
        event_type = call_args[0][0]
        payload = call_args[0][1]

        assert event_type == WebSocketEventType.SYSTEM_HEALTH_CHANGED

        # Verify payload structure matches SystemHealthChangedPayload schema
        assert "health" in payload
        assert "previous_health" in payload
        assert "components" in payload
        assert "timestamp" in payload

    @pytest.mark.asyncio
    async def test_system_error_payload_structure(
        self, health_emitter: HealthEventEmitter, mock_ws_emitter: MagicMock
    ) -> None:
        """Test system error event has correct payload structure."""
        from backend.core.websocket.event_types import WebSocketEventType

        health_emitter.set_emitter(mock_ws_emitter)

        await health_emitter.emit_system_error(
            error_code="TEST_ERROR",
            message="Test message",
            details={"key": "value"},
        )

        # Verify emit was called with correct event type
        call_args = mock_ws_emitter.emit.call_args
        event_type = call_args[0][0]
        payload = call_args[0][1]

        assert event_type == WebSocketEventType.SYSTEM_ERROR

        # Verify payload structure matches SystemErrorPayload schema
        assert "error" in payload
        assert "message" in payload
        assert "timestamp" in payload
        assert "details" in payload
        assert "recoverable" in payload


class TestConcurrency:
    """Tests for concurrent access safety."""

    @pytest.mark.asyncio
    async def test_concurrent_status_updates(
        self, health_emitter: HealthEventEmitter, mock_ws_emitter: MagicMock
    ) -> None:
        """Test concurrent status updates are handled safely."""
        import asyncio

        health_emitter.set_emitter(mock_ws_emitter)

        # Simulate concurrent updates
        async def update(component: str, status: str) -> bool:
            return await health_emitter.check_and_emit(component, status)

        results = await asyncio.gather(
            update("database", "healthy"),
            update("redis", "healthy"),
            update("ai_service", "degraded"),
            update("gpu", "healthy"),
            update("storage", "healthy"),
        )

        # All should have changed from UNKNOWN
        assert all(results)
        assert len(health_emitter._component_states) == 5
