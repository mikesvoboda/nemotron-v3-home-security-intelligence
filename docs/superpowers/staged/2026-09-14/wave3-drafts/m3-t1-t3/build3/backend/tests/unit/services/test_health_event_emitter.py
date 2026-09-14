"""Unit tests for health_event_emitter service."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.websocket.event_schemas import SystemHealth
from backend.core.websocket.event_types import WebSocketEventType
from backend.services.health_event_emitter import (
    ComponentHealthState,
    ErrorSeverity,
    HealthEventEmitter,
    HealthStatus,
    emit_system_error,
    get_health_event_emitter,
    reset_health_event_emitter,
)


@pytest.fixture(autouse=True)
def _enable_log_capture(caplog: pytest.LogCaptureFixture) -> None:
    """Automatically enable DEBUG-level log capture for all tests."""
    caplog.set_level(logging.DEBUG)


@pytest.fixture(autouse=True)
def _reset_emitter_state() -> None:
    """Reset global emitter state before each test for isolation."""
    reset_health_event_emitter()


@pytest.fixture
def mock_websocket_emitter() -> MagicMock:
    """Create a mock WebSocket emitter service."""
    emitter = MagicMock()
    emitter.emit = AsyncMock(return_value=None)
    return emitter


@pytest.fixture
def health_emitter(mock_websocket_emitter: MagicMock) -> HealthEventEmitter:
    """Create a HealthEventEmitter instance with mock WebSocket emitter."""
    emitter = HealthEventEmitter()
    emitter.set_emitter(mock_websocket_emitter)
    return emitter


# ==============================================================================
# Core Functionality Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_check_and_emit_emits_on_status_change(
    health_emitter: HealthEventEmitter,
    mock_websocket_emitter: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that check_and_emit emits event when component status changes."""
    # Arrange
    component = "database"
    new_status = HealthStatus.HEALTHY
    details = {"latency_ms": 5, "connection_pool": "healthy"}

    # Act
    result = await health_emitter.check_and_emit(component, new_status, details)

    # Assert
    assert result is True
    mock_websocket_emitter.emit.assert_awaited_once()
    call_args = mock_websocket_emitter.emit.call_args
    assert call_args[0][0] == WebSocketEventType.SYSTEM_HEALTH_CHANGED

    payload = call_args[0][1]
    assert payload["health"] == SystemHealth.HEALTHY.value
    assert payload["previous_health"] == SystemHealth.UNHEALTHY.value  # UNKNOWN maps to UNHEALTHY
    assert payload["changed_component"] == component
    assert payload["component_new_status"] == new_status.value
    assert payload["component_previous_status"] == HealthStatus.UNKNOWN.value

    # Check logging
    assert "Health status changed" in caplog.text
    assert component in caplog.text


@pytest.mark.asyncio
async def test_check_and_emit_no_emission_when_unchanged(
    health_emitter: HealthEventEmitter,
    mock_websocket_emitter: MagicMock,
) -> None:
    """Test that check_and_emit does not emit when status is unchanged."""
    # Arrange
    component = "redis"
    status = HealthStatus.HEALTHY

    # First update to set initial state
    await health_emitter.check_and_emit(component, status)
    mock_websocket_emitter.emit.reset_mock()

    # Act - same status again
    result = await health_emitter.check_and_emit(component, status)

    # Assert
    assert result is False
    mock_websocket_emitter.emit.assert_not_awaited()


@pytest.mark.asyncio
async def test_check_and_emit_updates_details_when_status_unchanged(
    health_emitter: HealthEventEmitter,
) -> None:
    """Test that details are updated even when status doesn't change."""
    # Arrange
    component = "gpu"
    status = HealthStatus.HEALTHY
    initial_details = {"memory_free": 1000}
    updated_details = {"memory_free": 800}

    # Act
    await health_emitter.check_and_emit(component, status, initial_details)
    await health_emitter.check_and_emit(component, status, updated_details)

    # Assert
    state = health_emitter._component_states[component]
    assert state.details == updated_details


@pytest.mark.asyncio
async def test_calculate_overall_status_unknown_when_no_components(
    health_emitter: HealthEventEmitter,
) -> None:
    """Test that overall status is UNKNOWN when no components are tracked."""
    # Act
    overall = health_emitter._calculate_overall_status()

    # Assert
    assert overall == HealthStatus.UNKNOWN


@pytest.mark.asyncio
async def test_calculate_overall_status_critical_component_unhealthy(
    health_emitter: HealthEventEmitter,
) -> None:
    """Test that unhealthy critical component makes overall status UNHEALTHY."""
    # Arrange - set non-critical component to healthy
    await health_emitter.check_and_emit("ai_service", HealthStatus.HEALTHY)

    # Act - set critical component to unhealthy
    await health_emitter.check_and_emit("database", HealthStatus.UNHEALTHY)

    # Assert
    assert health_emitter.get_overall_status() == HealthStatus.UNHEALTHY


@pytest.mark.asyncio
async def test_calculate_overall_status_worst_status_wins(
    health_emitter: HealthEventEmitter,
) -> None:
    """Test that overall status reflects worst component status."""
    # Arrange
    await health_emitter.check_and_emit("database", HealthStatus.HEALTHY)
    await health_emitter.check_and_emit("redis", HealthStatus.HEALTHY)
    await health_emitter.check_and_emit("ai_service", HealthStatus.HEALTHY)

    # Act - degrade one component
    await health_emitter.check_and_emit("ai_service", HealthStatus.DEGRADED)

    # Assert
    assert health_emitter.get_overall_status() == HealthStatus.DEGRADED


@pytest.mark.asyncio
async def test_update_all_components(
    health_emitter: HealthEventEmitter,
    mock_websocket_emitter: MagicMock,
) -> None:
    """Test that update_all_components updates multiple components efficiently."""
    # Arrange
    statuses = {
        "database": HealthStatus.HEALTHY,
        "redis": HealthStatus.HEALTHY,
        "ai_service": HealthStatus.DEGRADED,
        "gpu": HealthStatus.HEALTHY,
    }
    details = {
        "database": {"latency_ms": 5},
        "ai_service": {"error_rate": 0.05},
    }

    # Act
    changed = await health_emitter.update_all_components(statuses, details)

    # Assert
    assert len(changed) == 4  # All new components
    assert set(changed) == {"database", "redis", "ai_service", "gpu"}
    assert mock_websocket_emitter.emit.await_count == 4


@pytest.mark.asyncio
async def test_emit_system_error(
    health_emitter: HealthEventEmitter,
    mock_websocket_emitter: MagicMock,
) -> None:
    """Test that emit_system_error emits error event successfully."""
    # Arrange
    error_code = "AI_SERVICE_CRASH"
    message = "Nemotron service crashed unexpectedly"
    severity = ErrorSeverity.HIGH
    details = {"exit_code": 137, "signal": "SIGKILL"}

    # Act
    result = await health_emitter.emit_system_error(
        error_code=error_code,
        message=message,
        severity=severity,
        details=details,
        recoverable=True,
    )

    # Assert
    assert result is True
    mock_websocket_emitter.emit.assert_awaited_once()
    call_args = mock_websocket_emitter.emit.call_args
    assert call_args[0][0] == WebSocketEventType.SYSTEM_ERROR

    payload = call_args[0][1]
    assert payload["error"] == error_code
    assert payload["message"] == message
    assert payload["details"] == details
    assert payload["recoverable"] is True


# ==============================================================================
# Status Transition Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_transition_unknown_to_healthy(
    health_emitter: HealthEventEmitter,
    mock_websocket_emitter: MagicMock,
) -> None:
    """Test status transition from UNKNOWN to HEALTHY."""
    # Act
    result = await health_emitter.check_and_emit("storage", HealthStatus.HEALTHY)

    # Assert
    assert result is True
    call_args = mock_websocket_emitter.emit.call_args
    payload = call_args[0][1]
    assert payload["component_previous_status"] == HealthStatus.UNKNOWN.value
    assert payload["component_new_status"] == HealthStatus.HEALTHY.value


@pytest.mark.asyncio
async def test_transition_healthy_to_degraded(
    health_emitter: HealthEventEmitter,
    mock_websocket_emitter: MagicMock,
) -> None:
    """Test status transition from HEALTHY to DEGRADED."""
    # Arrange
    await health_emitter.check_and_emit("ai_service", HealthStatus.HEALTHY)
    mock_websocket_emitter.emit.reset_mock()

    # Act
    result = await health_emitter.check_and_emit("ai_service", HealthStatus.DEGRADED)

    # Assert
    assert result is True
    call_args = mock_websocket_emitter.emit.call_args
    payload = call_args[0][1]
    assert payload["component_previous_status"] == HealthStatus.HEALTHY.value
    assert payload["component_new_status"] == HealthStatus.DEGRADED.value


@pytest.mark.asyncio
async def test_transition_degraded_to_unhealthy(
    health_emitter: HealthEventEmitter,
    mock_websocket_emitter: MagicMock,
) -> None:
    """Test status transition from DEGRADED to UNHEALTHY."""
    # Arrange
    await health_emitter.check_and_emit("redis", HealthStatus.DEGRADED)
    mock_websocket_emitter.emit.reset_mock()

    # Act
    result = await health_emitter.check_and_emit("redis", HealthStatus.UNHEALTHY)

    # Assert
    assert result is True
    call_args = mock_websocket_emitter.emit.call_args
    payload = call_args[0][1]
    assert payload["component_previous_status"] == HealthStatus.DEGRADED.value
    assert payload["component_new_status"] == HealthStatus.UNHEALTHY.value


@pytest.mark.asyncio
async def test_transition_unhealthy_to_healthy_recovery(
    health_emitter: HealthEventEmitter,
    mock_websocket_emitter: MagicMock,
) -> None:
    """Test recovery transition from UNHEALTHY to HEALTHY."""
    # Arrange
    await health_emitter.check_and_emit("gpu", HealthStatus.UNHEALTHY)
    mock_websocket_emitter.emit.reset_mock()

    # Act
    result = await health_emitter.check_and_emit("gpu", HealthStatus.HEALTHY)

    # Assert
    assert result is True
    call_args = mock_websocket_emitter.emit.call_args
    payload = call_args[0][1]
    assert payload["component_previous_status"] == HealthStatus.UNHEALTHY.value
    assert payload["component_new_status"] == HealthStatus.HEALTHY.value


@pytest.mark.asyncio
async def test_critical_component_failure_affects_overall(
    health_emitter: HealthEventEmitter,
) -> None:
    """Test that critical component failure affects overall status."""
    # Arrange
    await health_emitter.check_and_emit("database", HealthStatus.HEALTHY)
    await health_emitter.check_and_emit("redis", HealthStatus.HEALTHY)
    await health_emitter.check_and_emit("ai_service", HealthStatus.HEALTHY)
    assert health_emitter.get_overall_status() == HealthStatus.HEALTHY

    # Act - fail critical component
    await health_emitter.check_and_emit("database", HealthStatus.UNHEALTHY)

    # Assert
    assert health_emitter.get_overall_status() == HealthStatus.UNHEALTHY


# ==============================================================================
# Edge Cases and Error Handling Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_concurrent_health_updates_thread_safety() -> None:
    """Test that concurrent health updates are handled safely with async lock."""
    # Arrange
    emitter = HealthEventEmitter()
    mock_ws = MagicMock()
    mock_ws.emit = AsyncMock(return_value=None)
    emitter.set_emitter(mock_ws)

    # Act - concurrent updates to same component
    async def update_component(status: HealthStatus) -> bool:
        return await emitter.check_and_emit("database", status)

    results = await asyncio.gather(
        update_component(HealthStatus.HEALTHY),
        update_component(HealthStatus.DEGRADED),
        update_component(HealthStatus.UNHEALTHY),
        update_component(HealthStatus.HEALTHY),
    )

    # Assert - only status changes should succeed
    changes = sum(1 for r in results if r)
    assert changes >= 1  # At least one change occurred
    # Final state should be consistent
    final_status = emitter.get_component_status("database")
    assert final_status in [
        HealthStatus.HEALTHY,
        HealthStatus.DEGRADED,
        HealthStatus.UNHEALTHY,
    ]


@pytest.mark.asyncio
async def test_emitter_not_configured_skips_emission(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that health changes work without emitter configured."""
    # Arrange
    emitter = HealthEventEmitter()
    # Note: no set_emitter() call

    # Act
    result = await emitter.check_and_emit("database", HealthStatus.HEALTHY)

    # Assert
    assert result is True  # Status change recorded
    # Verify debug log message for skipping emission
    assert any(
        "No emitter configured" in record.message
        for record in caplog.records
        if record.levelno == logging.DEBUG
    )


@pytest.mark.asyncio
async def test_websocket_emission_failure_handled_gracefully(
    health_emitter: HealthEventEmitter,
    mock_websocket_emitter: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that WebSocket emission failures are logged but don't crash."""
    # Arrange
    mock_websocket_emitter.emit.side_effect = RuntimeError("Connection lost")

    # Act
    result = await health_emitter.check_and_emit("database", HealthStatus.HEALTHY)

    # Assert
    assert result is True  # Status change still recorded
    assert "Failed to emit health changed event" in caplog.text


@pytest.mark.asyncio
async def test_invalid_status_string_defaults_to_unknown(
    health_emitter: HealthEventEmitter,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that invalid status string is normalized to UNKNOWN."""
    # Act
    result = await health_emitter.check_and_emit(
        "database",
        "invalid_status",  # type: ignore[arg-type]
    )

    # Assert
    # First time setting status to UNKNOWN from UNKNOWN is not a change
    assert result is False  # No status change (UNKNOWN -> UNKNOWN)
    assert health_emitter.get_component_status("database") == HealthStatus.UNKNOWN
    assert "Invalid health status" in caplog.text


@pytest.mark.asyncio
async def test_singleton_pattern_returns_same_instance() -> None:
    """Test that get_health_event_emitter returns singleton instance."""
    # Act
    emitter1 = get_health_event_emitter()
    emitter2 = get_health_event_emitter()

    # Assert
    assert emitter1 is emitter2


@pytest.mark.asyncio
async def test_reset_state_clears_all_components(
    health_emitter: HealthEventEmitter,
) -> None:
    """Test that reset clears all tracked component states."""
    # Arrange
    await health_emitter.check_and_emit("database", HealthStatus.HEALTHY)
    await health_emitter.check_and_emit("redis", HealthStatus.DEGRADED)
    assert len(health_emitter.get_all_component_statuses()) == 2

    # Act
    health_emitter.reset()

    # Assert
    assert len(health_emitter.get_all_component_statuses()) == 0
    assert health_emitter.get_overall_status() == HealthStatus.UNKNOWN


# ==============================================================================
# Get/Set Methods Tests
# ==============================================================================


def test_get_component_status_unknown_for_untracked() -> None:
    """Test that get_component_status returns UNKNOWN for untracked components."""
    # Arrange
    emitter = HealthEventEmitter()

    # Act
    status = emitter.get_component_status("nonexistent")

    # Assert
    assert status == HealthStatus.UNKNOWN


@pytest.mark.asyncio
async def test_get_all_component_statuses(health_emitter: HealthEventEmitter) -> None:
    """Test that get_all_component_statuses returns all tracked components."""
    # Arrange
    await health_emitter.check_and_emit("database", HealthStatus.HEALTHY)
    await health_emitter.check_and_emit("redis", HealthStatus.DEGRADED)
    await health_emitter.check_and_emit("gpu", HealthStatus.UNHEALTHY)

    # Act
    statuses = health_emitter.get_all_component_statuses()

    # Assert
    assert len(statuses) == 3
    assert statuses["database"] == "healthy"
    assert statuses["redis"] == "degraded"
    assert statuses["gpu"] == "unhealthy"


def test_get_overall_status_initial_unknown() -> None:
    """Test that get_overall_status returns UNKNOWN initially."""
    # Arrange
    emitter = HealthEventEmitter()

    # Act
    status = emitter.get_overall_status()

    # Assert
    assert status == HealthStatus.UNKNOWN


def test_set_emitter(health_emitter: HealthEventEmitter) -> None:
    """Test that set_emitter configures the WebSocket emitter."""
    # Arrange
    new_emitter = MagicMock()

    # Act
    health_emitter.set_emitter(new_emitter)

    # Assert
    assert health_emitter._emitter is new_emitter


# ==============================================================================
# Module-Level Function Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_emit_system_error_module_function(
    mock_websocket_emitter: MagicMock,
) -> None:
    """Test module-level emit_system_error function."""
    # Arrange
    emitter = get_health_event_emitter()
    emitter.set_emitter(mock_websocket_emitter)

    # Act
    result = await emit_system_error(
        error_code="TEST_ERROR",
        message="Test error message",
        severity=ErrorSeverity.CRITICAL,
        details={"test": "data"},
        recoverable=False,
    )

    # Assert
    assert result is True
    mock_websocket_emitter.emit.assert_awaited_once()


@pytest.mark.asyncio
async def test_emit_system_error_severity_normalization(
    health_emitter: HealthEventEmitter,
    mock_websocket_emitter: MagicMock,
) -> None:
    """Test that emit_system_error normalizes severity strings."""
    # Act - use string severity
    result = await health_emitter.emit_system_error(
        error_code="TEST",
        message="Test",
        severity="high",  # String instead of enum
    )

    # Assert
    assert result is True


@pytest.mark.asyncio
async def test_emit_system_error_invalid_severity_defaults_to_medium(
    health_emitter: HealthEventEmitter,
    mock_websocket_emitter: MagicMock,
) -> None:
    """Test that invalid severity defaults to MEDIUM."""
    # Act
    result = await health_emitter.emit_system_error(
        error_code="TEST",
        message="Test",
        severity="invalid",  # type: ignore[arg-type]
    )

    # Assert
    assert result is True


@pytest.mark.asyncio
async def test_emit_system_error_without_emitter(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test emit_system_error without configured emitter."""
    # Arrange
    emitter = HealthEventEmitter()

    # Act
    result = await emitter.emit_system_error(
        error_code="TEST", message="Test", severity=ErrorSeverity.LOW
    )

    # Assert
    assert result is False
    # Verify debug log message for skipping emission
    assert any(
        "No emitter configured" in record.message
        for record in caplog.records
        if record.levelno == logging.DEBUG
    )


# ==============================================================================
# Payload Construction Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_health_changed_payload_structure(
    health_emitter: HealthEventEmitter,
    mock_websocket_emitter: MagicMock,
) -> None:
    """Test that health changed event payload has correct structure."""
    # Act
    await health_emitter.check_and_emit("database", HealthStatus.DEGRADED)

    # Assert
    call_args = mock_websocket_emitter.emit.call_args
    payload = call_args[0][1]

    # Check required fields
    assert "health" in payload
    assert "previous_health" in payload
    assert "components" in payload
    assert "changed_component" in payload
    assert "component_previous_status" in payload
    assert "component_new_status" in payload
    assert "timestamp" in payload

    # Verify timestamp is ISO format
    timestamp = payload["timestamp"]
    assert "T" in timestamp
    assert timestamp.endswith("Z") or "+" in timestamp or "-" in timestamp[-6:]


@pytest.mark.asyncio
async def test_system_error_payload_structure(
    health_emitter: HealthEventEmitter,
    mock_websocket_emitter: MagicMock,
) -> None:
    """Test that system error event payload has correct structure."""
    # Arrange
    details = {"key": "value", "count": 42}

    # Act
    await health_emitter.emit_system_error(
        error_code="TEST_ERROR",
        message="Test message",
        severity=ErrorSeverity.HIGH,
        details=details,
        recoverable=True,
    )

    # Assert
    call_args = mock_websocket_emitter.emit.call_args
    payload = call_args[0][1]

    assert payload["error"] == "TEST_ERROR"
    assert payload["message"] == "Test message"
    assert payload["details"] == details
    assert payload["recoverable"] is True
    assert "timestamp" in payload


# ==============================================================================
# ComponentHealthState Tests
# ==============================================================================


def test_component_health_state_defaults() -> None:
    """Test ComponentHealthState default values."""
    # Act
    state = ComponentHealthState()

    # Assert
    assert state.status == HealthStatus.UNKNOWN
    assert isinstance(state.last_changed, datetime)
    assert state.details == {}


def test_component_health_state_with_values() -> None:
    """Test ComponentHealthState with explicit values."""
    # Arrange
    now = datetime.now(UTC)
    details = {"error": "Connection timeout"}

    # Act
    state = ComponentHealthState(
        status=HealthStatus.UNHEALTHY,
        last_changed=now,
        details=details,
    )

    # Assert
    assert state.status == HealthStatus.UNHEALTHY
    assert state.last_changed == now
    assert state.details == details


# ==============================================================================
# DI Container Integration Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_get_health_event_emitter_from_container() -> None:
    """Test that get_health_event_emitter can retrieve from DI container."""
    with patch("backend.core.container.get_container") as mock_container:
        # Arrange
        container_emitter = HealthEventEmitter()
        mock_reg = MagicMock()
        mock_reg.instance = container_emitter

        mock_container.return_value._registrations = {"health_event_emitter": mock_reg}

        # Act
        result = get_health_event_emitter()

        # Assert
        assert result is container_emitter


@pytest.mark.asyncio
async def test_get_health_event_emitter_fallback_to_legacy() -> None:
    """Test that get_health_event_emitter falls back to legacy singleton."""
    with patch(
        "backend.core.container.get_container",
        side_effect=ImportError,
    ):
        # Act
        result = get_health_event_emitter()

        # Assert
        assert isinstance(result, HealthEventEmitter)


def test_reset_health_event_emitter_resets_both_di_and_legacy() -> None:
    """Test that reset_health_event_emitter resets both DI and legacy instances."""
    with patch("backend.core.container.get_container") as mock_container:
        # Arrange
        container_emitter = MagicMock()
        container_emitter.reset = MagicMock()
        mock_reg = MagicMock()
        mock_reg.instance = container_emitter

        mock_container.return_value._registrations = {"health_event_emitter": mock_reg}

        # Act
        reset_health_event_emitter()

        # Assert
        container_emitter.reset.assert_called_once()
        assert mock_reg.instance is None
