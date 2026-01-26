"""Unit tests for main.py initialization functions.

Tests cover:
- init_circuit_breakers() pre-registration of known service circuit breakers
- Signal handling for graceful shutdown (SIGTERM/SIGINT)
- Shutdown event coordination
"""

from __future__ import annotations

import asyncio
import signal
from unittest.mock import MagicMock, patch

import pytest

from backend.services.circuit_breaker import (
    _get_registry,
    reset_circuit_breaker_registry,
)


@pytest.fixture(autouse=True)
def reset_global_registry():
    """Reset global registry before and after each test."""
    reset_circuit_breaker_registry()
    yield
    reset_circuit_breaker_registry()


class TestInitCircuitBreakers:
    """Tests for init_circuit_breakers() function."""

    def test_pre_registers_known_services(self) -> None:
        """Test that init_circuit_breakers registers all known services."""
        from backend.main import init_circuit_breakers

        breaker_names = init_circuit_breakers()

        # Should return all 4 known services
        assert len(breaker_names) == 4
        assert "yolo26" in breaker_names
        assert "nemotron" in breaker_names
        assert "postgresql" in breaker_names
        assert "redis" in breaker_names

    def test_circuit_breakers_appear_in_registry(self) -> None:
        """Test that circuit breakers are registered in global registry."""
        from backend.main import init_circuit_breakers

        init_circuit_breakers()

        registry = _get_registry()
        all_status = registry.get_all_status()

        assert "yolo26" in all_status
        assert "nemotron" in all_status
        assert "postgresql" in all_status
        assert "redis" in all_status

    def test_ai_service_config_has_lower_threshold(self) -> None:
        """Test that AI services have more aggressive (lower) failure threshold."""
        from backend.main import init_circuit_breakers

        init_circuit_breakers()

        registry = _get_registry()
        all_status = registry.get_all_status()

        # AI services should have failure_threshold=5
        rtdetr_config = all_status["yolo26"]["config"]
        nemotron_config = all_status["nemotron"]["config"]
        assert rtdetr_config["failure_threshold"] == 5
        assert nemotron_config["failure_threshold"] == 5

    def test_infrastructure_service_config_has_higher_threshold(self) -> None:
        """Test that infrastructure services have higher failure threshold."""
        from backend.main import init_circuit_breakers

        init_circuit_breakers()

        registry = _get_registry()
        all_status = registry.get_all_status()

        # Infrastructure services should have failure_threshold=10
        postgresql_config = all_status["postgresql"]["config"]
        redis_config = all_status["redis"]["config"]
        assert postgresql_config["failure_threshold"] == 10
        assert redis_config["failure_threshold"] == 10

    def test_all_circuit_breakers_start_closed(self) -> None:
        """Test that all circuit breakers start in CLOSED state."""
        from backend.main import init_circuit_breakers

        init_circuit_breakers()

        registry = _get_registry()
        all_status = registry.get_all_status()

        for name, status in all_status.items():
            assert status["state"] == "closed", f"{name} should be in closed state"

    def test_idempotent_registration(self) -> None:
        """Test that calling init_circuit_breakers multiple times is safe."""
        from backend.main import init_circuit_breakers

        # Call multiple times
        first_result = init_circuit_breakers()
        second_result = init_circuit_breakers()

        # Should return same names
        assert first_result == second_result

        # Registry should still have exactly 4 circuit breakers
        registry = _get_registry()
        all_status = registry.get_all_status()
        assert len(all_status) == 4


@pytest.fixture
def reset_signal_handler_state():
    """Reset signal handler state before and after each test."""
    from backend.main import reset_signal_handlers

    reset_signal_handlers()
    yield
    reset_signal_handlers()


class TestGetShutdownEvent:
    """Tests for get_shutdown_event() function."""

    def test_returns_asyncio_event(self, reset_signal_handler_state: None) -> None:
        """Test that get_shutdown_event returns an asyncio.Event."""
        from backend.main import get_shutdown_event

        event = get_shutdown_event()

        assert isinstance(event, asyncio.Event)
        assert not event.is_set()

    def test_returns_same_event_on_multiple_calls(self, reset_signal_handler_state: None) -> None:
        """Test that get_shutdown_event returns the same event on multiple calls."""
        from backend.main import get_shutdown_event

        event1 = get_shutdown_event()
        event2 = get_shutdown_event()

        assert event1 is event2

    def test_event_can_be_set(self, reset_signal_handler_state: None) -> None:
        """Test that the shutdown event can be set."""
        from backend.main import get_shutdown_event

        event = get_shutdown_event()
        assert not event.is_set()

        event.set()
        assert event.is_set()


class TestInstallSignalHandlers:
    """Tests for install_signal_handlers() function."""

    @pytest.mark.asyncio
    async def test_installs_sigterm_handler(self, reset_signal_handler_state: None) -> None:
        """Test that SIGTERM handler is installed."""
        from backend.main import install_signal_handlers

        mock_loop = MagicMock()
        captured_handlers: dict[signal.Signals, MagicMock] = {}

        def capture_handler(sig: signal.Signals, handler: MagicMock) -> None:
            captured_handlers[sig] = handler

        mock_loop.add_signal_handler = capture_handler

        with patch("asyncio.get_running_loop", return_value=mock_loop):
            install_signal_handlers()

        assert signal.SIGTERM in captured_handlers

    @pytest.mark.asyncio
    async def test_installs_sigint_handler(self, reset_signal_handler_state: None) -> None:
        """Test that SIGINT handler is installed."""
        from backend.main import install_signal_handlers

        mock_loop = MagicMock()
        captured_handlers: dict[signal.Signals, MagicMock] = {}

        def capture_handler(sig: signal.Signals, handler: MagicMock) -> None:
            captured_handlers[sig] = handler

        mock_loop.add_signal_handler = capture_handler

        with patch("asyncio.get_running_loop", return_value=mock_loop):
            install_signal_handlers()

        assert signal.SIGINT in captured_handlers

    @pytest.mark.asyncio
    async def test_handler_sets_shutdown_event(self, reset_signal_handler_state: None) -> None:
        """Test that signal handler sets the shutdown event."""
        from backend.main import get_shutdown_event, install_signal_handlers

        mock_loop = MagicMock()
        captured_handlers: dict[signal.Signals, MagicMock] = {}

        def capture_handler(sig: signal.Signals, handler: MagicMock) -> None:
            captured_handlers[sig] = handler

        mock_loop.add_signal_handler = capture_handler

        with patch("asyncio.get_running_loop", return_value=mock_loop):
            install_signal_handlers()

        # Get the shutdown event
        event = get_shutdown_event()
        assert not event.is_set()

        # Call the SIGTERM handler - the logger is imported inside the function
        # so we patch at the source module
        with patch("backend.core.logging.get_logger"):
            captured_handlers[signal.SIGTERM]()

        # Event should be set
        assert event.is_set()

    @pytest.mark.asyncio
    async def test_idempotent_installation(self, reset_signal_handler_state: None) -> None:
        """Test that calling install_signal_handlers multiple times is safe."""
        from backend.main import install_signal_handlers

        mock_loop = MagicMock()
        call_count = 0

        def count_handler(sig: signal.Signals, handler: MagicMock) -> None:
            nonlocal call_count
            call_count += 1

        mock_loop.add_signal_handler = count_handler

        with patch("asyncio.get_running_loop", return_value=mock_loop):
            install_signal_handlers()
            install_signal_handlers()
            install_signal_handlers()

        # Should only install handlers once (2 handlers: SIGTERM and SIGINT)
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_handles_not_implemented_error(self, reset_signal_handler_state: None) -> None:
        """Test that NotImplementedError is handled gracefully (e.g., Windows)."""
        from backend.main import install_signal_handlers

        mock_loop = MagicMock()
        mock_loop.add_signal_handler.side_effect = NotImplementedError(
            "Signals not supported on Windows"
        )

        with patch("asyncio.get_running_loop", return_value=mock_loop):
            # Should not raise
            install_signal_handlers()

    @pytest.mark.asyncio
    async def test_handles_runtime_error(self, reset_signal_handler_state: None) -> None:
        """Test that RuntimeError is handled gracefully (e.g., not main thread)."""
        from backend.main import install_signal_handlers

        with patch("asyncio.get_running_loop", side_effect=RuntimeError("no running event loop")):
            # Should not raise
            install_signal_handlers()


class TestResetSignalHandlers:
    """Tests for reset_signal_handlers() function."""

    def test_resets_shutdown_event(self) -> None:
        """Test that reset_signal_handlers clears the shutdown event."""
        from backend.main import get_shutdown_event, reset_signal_handlers

        # Create and set the event
        event1 = get_shutdown_event()
        event1.set()

        # Reset
        reset_signal_handlers()

        # New event should be created
        event2 = get_shutdown_event()
        assert event2 is not event1
        assert not event2.is_set()

    @pytest.mark.asyncio
    async def test_allows_reinstallation_of_handlers(self) -> None:
        """Test that after reset, handlers can be installed again."""
        from backend.main import install_signal_handlers, reset_signal_handlers

        mock_loop = MagicMock()
        call_count = 0

        def count_handler(sig: signal.Signals, handler: MagicMock) -> None:
            nonlocal call_count
            call_count += 1

        mock_loop.add_signal_handler = count_handler

        with patch("asyncio.get_running_loop", return_value=mock_loop):
            install_signal_handlers()
            assert call_count == 2  # SIGTERM and SIGINT

            reset_signal_handlers()

            install_signal_handlers()
            assert call_count == 4  # Should install again after reset
