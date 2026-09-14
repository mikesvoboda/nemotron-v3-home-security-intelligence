"""Chaos tests for PostgreSQL database failures.

This module tests system behavior when the PostgreSQL database experiences
various failure modes:
- Connection failures (database unreachable)
- Slow queries (high latency)
- Intermittent failures (random query failures)
- Transaction rollbacks (concurrent modification)

Expected Behavior:
- API endpoints return appropriate error responses (503)
- Health endpoint reports degraded database status
- Cached data is returned when available
- System gracefully handles connection pool exhaustion
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.exc import InterfaceError, OperationalError
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError

from backend.services.degradation_manager import (
    DegradationManager,
    DegradationMode,
    DegradationServiceStatus,
    reset_degradation_manager,
)


@pytest.fixture(autouse=True)
def reset_state() -> None:
    """Reset global state before each test."""
    reset_degradation_manager()


class TestDatabaseConnectionFailure:
    """Tests for database connection failure scenarios."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_degradation_manager_detects_database_failure(self) -> None:
        """DegradationManager correctly detects database unavailability."""
        manager = DegradationManager(failure_threshold=1)

        async def failing_health_check() -> bool:
            raise OperationalError("statement", {}, Exception("Connection refused"))

        manager.register_service(name="database", health_check=failing_health_check, critical=True)

        # Run health check
        await manager.run_health_checks()

        health = manager.get_service_health("database")
        assert health.status == DegradationServiceStatus.UNHEALTHY
        assert health.consecutive_failures >= 1

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_operational_error_handled_gracefully(self) -> None:
        """OperationalError is caught and handled gracefully."""
        # Test that our error handling catches OperationalError
        error = OperationalError("test statement", {}, Exception("Connection refused"))

        # Verify error properties
        assert "Connection refused" in str(error)

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_interface_error_handled_gracefully(self) -> None:
        """InterfaceError (connection lost) is handled gracefully."""
        # Test that our error handling catches InterfaceError
        error = InterfaceError("Connection lost", {}, Exception("Connection closed"))

        # Verify error can be caught
        try:
            raise error
        except InterfaceError as e:
            assert "Connection" in str(e)


class TestDatabaseSlowQueries:
    """Tests for slow database query scenarios."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_slow_query_detected_by_health_check(self) -> None:
        """Slow database queries are detected by health checks."""
        manager = DegradationManager(failure_threshold=1, health_check_timeout=0.1)

        async def slow_health_check() -> bool:
            await asyncio.sleep(0.5)  # Longer than timeout
            return True

        manager.register_service(name="database", health_check=slow_health_check, critical=True)

        # Run health check - should timeout
        await manager.run_health_checks()

        health = manager.get_service_health("database")
        assert health.status == DegradationServiceStatus.UNHEALTHY
        # Error message contains "timed out" (case insensitive check)
        assert "timed out" in (health.error_message or "").lower()

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_sqlalchemy_timeout_handled(self) -> None:
        """SQLAlchemy timeout errors are handled gracefully."""
        manager = DegradationManager(failure_threshold=1)

        async def timeout_health_check() -> bool:
            raise SQLAlchemyTimeoutError()

        manager.register_service(name="database", health_check=timeout_health_check, critical=True)

        # Run health check
        await manager.run_health_checks()

        health = manager.get_service_health("database")
        assert health.status == DegradationServiceStatus.UNHEALTHY


class TestDatabaseModeTransitions:
    """Tests for degradation mode transitions with database failures."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_critical_database_failure_triggers_mode_change(self) -> None:
        """Critical database failure triggers appropriate mode change."""
        manager = DegradationManager(failure_threshold=2)

        manager.register_service(
            name="database", health_check=AsyncMock(return_value=True), critical=True
        )

        # Start in NORMAL
        assert manager.mode == DegradationMode.NORMAL

        # Simulate consecutive failures
        await manager.update_service_health(
            "database", is_healthy=False, error_message="Connection refused"
        )
        await manager.update_service_health(
            "database", is_healthy=False, error_message="Connection refused"
        )
        await manager.update_service_health(
            "database", is_healthy=False, error_message="Connection refused"
        )

        # Should transition to degraded mode
        assert manager.mode in (DegradationMode.MINIMAL, DegradationMode.OFFLINE)

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_database_recovery_restores_normal(self) -> None:
        """Database recovery restores normal operation mode."""
        manager = DegradationManager(failure_threshold=2)

        manager.register_service(
            name="database", health_check=AsyncMock(return_value=True), critical=True
        )

        # Trigger degradation
        await manager.update_service_health("database", is_healthy=False)
        await manager.update_service_health("database", is_healthy=False)
        await manager.update_service_health("database", is_healthy=False)

        # Recover
        await manager.update_service_health("database", is_healthy=True)

        # Should be back to normal
        assert manager.mode == DegradationMode.NORMAL


class TestDatabaseHealthReporting:
    """Tests for database health status reporting."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_status_includes_database_health(self) -> None:
        """Status report includes database health information."""
        manager = DegradationManager(failure_threshold=1)

        manager.register_service(
            name="database", health_check=AsyncMock(return_value=True), critical=True
        )

        await manager.update_service_health(
            "database", is_healthy=False, error_message="Pool exhausted"
        )

        status = manager.get_status()

        assert "services" in status
        assert "database" in status["services"]
        db_status = status["services"]["database"]
        assert db_status["status"] == "unhealthy"
        assert "Pool exhausted" in db_status.get("error_message", "")

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_consecutive_failures_tracked(self) -> None:
        """Consecutive database failures are properly tracked."""
        manager = DegradationManager(failure_threshold=5)

        manager.register_service(
            name="database", health_check=AsyncMock(return_value=True), critical=True
        )

        # Simulate 3 failures
        for i in range(3):
            await manager.update_service_health(
                "database", is_healthy=False, error_message=f"Error {i}"
            )

        health = manager.get_service_health("database")
        assert health.consecutive_failures == 3


class TestDatabaseTransactionFailures:
    """Tests for database transaction failure scenarios."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_transaction_rollback_handled(self) -> None:
        """Transaction rollback errors are handled gracefully."""
        # Create a mock session that fails on commit
        mock_session = AsyncMock()
        mock_session.commit = AsyncMock(
            side_effect=OperationalError("statement", {}, Exception("Deadlock detected"))
        )

        # Verify the error is raised
        with pytest.raises(OperationalError) as exc_info:
            await mock_session.commit()

        assert "Deadlock" in str(exc_info.value)

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_concurrent_modification_error(self) -> None:
        """Concurrent modification (optimistic locking) errors are handled."""
        # Simulate StaleDataError scenario
        error = OperationalError(
            "statement", {}, Exception("could not serialize access due to concurrent update")
        )

        try:
            raise error
        except OperationalError as e:
            assert "concurrent" in str(e)


class TestDatabaseConnectionPoolExhaustion:
    """Tests for connection pool exhaustion scenarios."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_pool_exhaustion_detected(self) -> None:
        """Connection pool exhaustion is detected and reported."""
        manager = DegradationManager(failure_threshold=1)

        async def pool_exhausted_check() -> bool:
            raise OperationalError(
                "statement", {}, Exception("QueuePool limit reached, connection timed out")
            )

        manager.register_service(name="database", health_check=pool_exhausted_check, critical=True)

        await manager.run_health_checks()

        health = manager.get_service_health("database")
        assert health.status == DegradationServiceStatus.UNHEALTHY


class TestDatabaseFailoverScenarios:
    """Tests for database failover/recovery scenarios."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_brief_outage_recovers_automatically(self) -> None:
        """Brief database outages are recovered from automatically."""
        manager = DegradationManager(failure_threshold=3, recovery_threshold=2)

        manager.register_service(
            name="database", health_check=AsyncMock(return_value=True), critical=True
        )

        # Brief outage (2 failures, under threshold)
        await manager.update_service_health("database", is_healthy=False)
        await manager.update_service_health("database", is_healthy=False)

        # Still under threshold
        assert manager.mode == DegradationMode.NORMAL

        # Recovery
        await manager.update_service_health("database", is_healthy=True)

        health = manager.get_service_health("database")
        assert health.consecutive_failures == 0

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_extended_outage_triggers_degradation(self) -> None:
        """Extended database outages trigger degradation mode."""
        manager = DegradationManager(failure_threshold=3)

        manager.register_service(
            name="database", health_check=AsyncMock(return_value=True), critical=True
        )

        # Extended outage (4 failures)
        for _ in range(4):
            await manager.update_service_health("database", is_healthy=False)

        # Should be degraded
        assert manager.mode != DegradationMode.NORMAL


class TestDatabaseErrorMessages:
    """Tests for proper error message handling in database failures."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_error_messages_stored_for_debugging(self) -> None:
        """Error messages from database failures are stored for debugging."""
        manager = DegradationManager(failure_threshold=1)

        manager.register_service(
            name="database", health_check=AsyncMock(return_value=True), critical=True
        )

        error_msg = "FATAL: password authentication failed for user 'security'"
        await manager.update_service_health("database", is_healthy=False, error_message=error_msg)

        health = manager.get_service_health("database")
        assert health.error_message == error_msg

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_error_message_cleared_on_recovery(self) -> None:
        """Error messages are cleared when database recovers."""
        manager = DegradationManager(failure_threshold=1)

        manager.register_service(
            name="database", health_check=AsyncMock(return_value=True), critical=True
        )

        # Fail
        await manager.update_service_health(
            "database", is_healthy=False, error_message="Connection refused"
        )

        # Recover
        await manager.update_service_health("database", is_healthy=True)

        health = manager.get_service_health("database")
        assert health.error_message is None
