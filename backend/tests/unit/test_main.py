"""Unit tests for main.py initialization functions.

Tests cover:
- init_circuit_breakers() pre-registration of known service circuit breakers
"""

from __future__ import annotations

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
        assert "rtdetr" in breaker_names
        assert "nemotron" in breaker_names
        assert "postgresql" in breaker_names
        assert "redis" in breaker_names

    def test_circuit_breakers_appear_in_registry(self) -> None:
        """Test that circuit breakers are registered in global registry."""
        from backend.main import init_circuit_breakers

        init_circuit_breakers()

        registry = _get_registry()
        all_status = registry.get_all_status()

        assert "rtdetr" in all_status
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
        rtdetr_config = all_status["rtdetr"]["config"]
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
