"""Unit tests for HealthServiceRegistry (NEM-2611).

These tests verify:
- Service registration and isolation
- Worker status reporting
- Circuit breaker functionality
- DI container integration
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.health_service_registry import (
    HealthCircuitBreaker,
    HealthServiceRegistry,
    WorkerStatus,
    get_health_registry,
    get_health_registry_optional,
)


class TestHealthCircuitBreaker:
    """Tests for the HealthCircuitBreaker class."""

    def test_initial_state_is_closed(self) -> None:
        """Circuit breaker should start in closed state."""
        cb = HealthCircuitBreaker()
        assert cb.get_state("test_service") == "closed"
        assert not cb.is_open("test_service")

    def test_record_failure_opens_circuit_after_threshold(self) -> None:
        """Circuit should open after failure threshold is reached."""
        cb = HealthCircuitBreaker(failure_threshold=3)

        # Record failures
        cb.record_failure("test_service", "Error 1")
        assert not cb.is_open("test_service")

        cb.record_failure("test_service", "Error 2")
        assert not cb.is_open("test_service")

        cb.record_failure("test_service", "Error 3")
        assert cb.is_open("test_service")
        assert cb.get_state("test_service") == "open"

    def test_record_success_resets_failures(self) -> None:
        """Recording success should reset failure count."""
        cb = HealthCircuitBreaker(failure_threshold=3)

        cb.record_failure("test_service", "Error 1")
        cb.record_failure("test_service", "Error 2")

        cb.record_success("test_service")

        # Should need 3 more failures to open
        cb.record_failure("test_service", "Error 1")
        cb.record_failure("test_service", "Error 2")
        assert not cb.is_open("test_service")

    def test_cached_error_available_when_open(self) -> None:
        """Last error should be cached when circuit is open."""
        cb = HealthCircuitBreaker(failure_threshold=2)

        cb.record_failure("test_service", "First error")
        cb.record_failure("test_service", "Second error")

        assert cb.get_cached_error("test_service") == "Second error"

    def test_cached_error_cleared_on_success(self) -> None:
        """Cached error should be cleared when success is recorded."""
        cb = HealthCircuitBreaker(failure_threshold=2)

        cb.record_failure("test_service", "Error")
        cb.record_failure("test_service", "Error")

        cb.record_success("test_service")
        assert cb.get_cached_error("test_service") is None

    def test_circuit_resets_after_timeout(self) -> None:
        """Circuit should reset after timeout period."""
        cb = HealthCircuitBreaker(
            failure_threshold=2,
            reset_timeout=timedelta(seconds=0),  # Immediate reset for testing
        )

        cb.record_failure("test_service", "Error 1")
        cb.record_failure("test_service", "Error 2")

        # Circuit should reset immediately due to 0-second timeout
        assert not cb.is_open("test_service")

    def test_multiple_services_isolated(self) -> None:
        """Different services should have isolated circuit breakers."""
        cb = HealthCircuitBreaker(failure_threshold=2)

        # Fail service_a
        cb.record_failure("service_a", "Error")
        cb.record_failure("service_a", "Error")

        # service_a is open, service_b is still closed
        assert cb.is_open("service_a")
        assert not cb.is_open("service_b")

        # Success on service_b doesn't affect service_a
        cb.record_success("service_b")
        assert cb.is_open("service_a")


class TestHealthServiceRegistry:
    """Tests for the HealthServiceRegistry class."""

    def test_initialization_with_no_services(self) -> None:
        """Registry should initialize with no services."""
        registry = HealthServiceRegistry()

        assert registry.gpu_monitor is None
        assert registry.cleanup_service is None
        assert registry.system_broadcaster is None
        assert registry.file_watcher is None
        assert registry.pipeline_manager is None
        assert registry.batch_aggregator is None
        assert registry.degradation_manager is None
        assert registry.service_health_monitor is None
        assert registry.performance_collector is None
        assert registry.health_event_emitter is None

    def test_initialization_with_services(self) -> None:
        """Registry should accept services in constructor."""
        mock_gpu = MagicMock()
        mock_cleanup = MagicMock()

        registry = HealthServiceRegistry(
            gpu_monitor=mock_gpu,
            cleanup_service=mock_cleanup,
        )

        assert registry.gpu_monitor is mock_gpu
        assert registry.cleanup_service is mock_cleanup

    def test_register_services_individually(self) -> None:
        """Services should be registrable individually."""
        registry = HealthServiceRegistry()

        mock_gpu = MagicMock()
        registry.register_gpu_monitor(mock_gpu)
        assert registry.gpu_monitor is mock_gpu

        mock_cleanup = MagicMock()
        registry.register_cleanup_service(mock_cleanup)
        assert registry.cleanup_service is mock_cleanup

    def test_get_worker_statuses_with_running_services(self) -> None:
        """Worker statuses should reflect running services."""
        mock_gpu = MagicMock()
        mock_gpu.running = True

        mock_cleanup = MagicMock()
        mock_cleanup.running = False

        registry = HealthServiceRegistry(
            gpu_monitor=mock_gpu,
            cleanup_service=mock_cleanup,
        )

        statuses = registry.get_worker_statuses()

        # Find statuses by name
        gpu_status = next((s for s in statuses if s.name == "gpu_monitor"), None)
        cleanup_status = next((s for s in statuses if s.name == "cleanup_service"), None)

        assert gpu_status is not None
        assert gpu_status.running is True
        assert gpu_status.message is None

        assert cleanup_status is not None
        assert cleanup_status.running is False
        assert cleanup_status.message == "Not running"

    def test_get_worker_statuses_with_pipeline_manager(self) -> None:
        """Worker statuses should include pipeline workers."""
        mock_pipeline = MagicMock()
        mock_pipeline.get_status.return_value = {
            "workers": {
                "detection": {"state": "running"},
                "analysis": {"state": "stopped"},
                "batch_timeout": {"state": "running"},
            }
        }

        registry = HealthServiceRegistry(pipeline_manager=mock_pipeline)

        statuses = registry.get_worker_statuses()

        detection_status = next((s for s in statuses if s.name == "detection_worker"), None)
        analysis_status = next((s for s in statuses if s.name == "analysis_worker"), None)
        batch_status = next((s for s in statuses if s.name == "batch_timeout_worker"), None)

        assert detection_status is not None
        assert detection_status.running is True

        assert analysis_status is not None
        assert analysis_status.running is False
        assert analysis_status.message == "State: stopped"

        assert batch_status is not None
        assert batch_status.running is True

    def test_are_critical_pipeline_workers_healthy(self) -> None:
        """Critical worker health check should require detection and analysis."""
        mock_pipeline = MagicMock()

        # Both running
        mock_pipeline.get_status.return_value = {
            "workers": {
                "detection": {"state": "running"},
                "analysis": {"state": "running"},
            }
        }
        registry = HealthServiceRegistry(pipeline_manager=mock_pipeline)
        assert registry.are_critical_pipeline_workers_healthy() is True

        # Detection stopped
        mock_pipeline.get_status.return_value = {
            "workers": {
                "detection": {"state": "stopped"},
                "analysis": {"state": "running"},
            }
        }
        assert registry.are_critical_pipeline_workers_healthy() is False

        # Analysis stopped
        mock_pipeline.get_status.return_value = {
            "workers": {
                "detection": {"state": "running"},
                "analysis": {"state": "stopped"},
            }
        }
        assert registry.are_critical_pipeline_workers_healthy() is False

    def test_are_critical_pipeline_workers_healthy_without_manager(self) -> None:
        """Critical worker health should be False when manager is None."""
        registry = HealthServiceRegistry()
        assert registry.are_critical_pipeline_workers_healthy() is False

    def test_circuit_breaker_property(self) -> None:
        """Registry should have a circuit breaker property."""
        registry = HealthServiceRegistry()
        assert isinstance(registry.circuit_breaker, HealthCircuitBreaker)

    def test_has_batch_aggregator(self) -> None:
        """has_batch_aggregator should return True when registered."""
        mock_aggregator = MagicMock()

        registry = HealthServiceRegistry(batch_aggregator=mock_aggregator)
        assert registry.has_batch_aggregator() is True

    def test_has_batch_aggregator_false(self) -> None:
        """has_batch_aggregator should return False when not registered."""
        registry = HealthServiceRegistry()
        assert registry.has_batch_aggregator() is False

    def test_has_degradation_manager(self) -> None:
        """has_degradation_manager should return True when registered."""
        mock_degradation = MagicMock()

        registry = HealthServiceRegistry(degradation_manager=mock_degradation)
        assert registry.has_degradation_manager() is True

    def test_has_degradation_manager_false(self) -> None:
        """has_degradation_manager should return False when not registered."""
        registry = HealthServiceRegistry()
        assert registry.has_degradation_manager() is False

    def test_get_health_events(self) -> None:
        """Health events should be returned from service health monitor."""
        mock_monitor = MagicMock()
        mock_monitor.get_recent_events.return_value = [
            MagicMock(service="test", event_type="failure")
        ]

        registry = HealthServiceRegistry(service_health_monitor=mock_monitor)
        events = registry.get_health_events(limit=10)

        assert len(events) == 1
        mock_monitor.get_recent_events.assert_called_once_with(limit=10)

    def test_get_health_events_without_monitor(self) -> None:
        """Health events should be empty when monitor is None."""
        registry = HealthServiceRegistry()
        assert registry.get_health_events() == []


class TestWorkerStatus:
    """Tests for the WorkerStatus dataclass."""

    def test_worker_status_creation(self) -> None:
        """WorkerStatus should be created with name and running status."""
        status = WorkerStatus(name="test_worker", running=True)
        assert status.name == "test_worker"
        assert status.running is True
        assert status.message is None

    def test_worker_status_with_message(self) -> None:
        """WorkerStatus should support optional message."""
        status = WorkerStatus(name="test_worker", running=False, message="Stopped by user")
        assert status.message == "Stopped by user"


class TestServiceIsolation:
    """Tests verifying service isolation between instances."""

    def test_separate_registries_are_isolated(self) -> None:
        """Separate registry instances should be isolated."""
        mock_gpu1 = MagicMock()
        mock_gpu2 = MagicMock()

        registry1 = HealthServiceRegistry(gpu_monitor=mock_gpu1)
        registry2 = HealthServiceRegistry(gpu_monitor=mock_gpu2)

        assert registry1.gpu_monitor is mock_gpu1
        assert registry2.gpu_monitor is mock_gpu2
        assert registry1.gpu_monitor is not registry2.gpu_monitor

    def test_circuit_breakers_isolated_per_registry(self) -> None:
        """Each registry should have its own circuit breaker."""
        registry1 = HealthServiceRegistry()
        registry2 = HealthServiceRegistry()

        # Fail service in registry1
        registry1.circuit_breaker.record_failure("test", "Error")
        registry1.circuit_breaker.record_failure("test", "Error")
        registry1.circuit_breaker.record_failure("test", "Error")

        # Registry1 circuit is open, registry2 is closed
        assert registry1.circuit_breaker.is_open("test")
        assert not registry2.circuit_breaker.is_open("test")


class TestDIContainerIntegration:
    """Tests for DI container integration."""

    @pytest.mark.asyncio
    async def test_get_health_registry_from_container(self) -> None:
        """get_health_registry should retrieve registry from container."""
        mock_registry = MagicMock()

        with patch("backend.core.container.get_container") as mock_get:
            mock_container = MagicMock()
            mock_container.get_async = AsyncMock(return_value=mock_registry)
            mock_get.return_value = mock_container

            result = await get_health_registry()
            assert result is mock_registry

    def test_get_health_registry_optional_returns_none_when_not_available(self) -> None:
        """get_health_registry_optional should return None when not available."""
        with patch("backend.core.container.get_container") as mock_get:
            mock_container = MagicMock()
            mock_container._registrations = {}
            mock_get.return_value = mock_container

            result = get_health_registry_optional()
            assert result is None

    def test_get_health_registry_optional_returns_instance(self) -> None:
        """get_health_registry_optional should return instance when available."""
        mock_registry = MagicMock()

        with patch("backend.core.container.get_container") as mock_get:
            mock_container = MagicMock()
            mock_registration = MagicMock()
            mock_registration.instance = mock_registry
            mock_container._registrations = {"health_service_registry": mock_registration}
            mock_get.return_value = mock_container

            result = get_health_registry_optional()
            assert result is mock_registry
