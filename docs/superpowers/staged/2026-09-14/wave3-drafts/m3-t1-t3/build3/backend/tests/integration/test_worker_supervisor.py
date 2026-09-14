"""Integration tests for WorkerSupervisor service (NEM-2457).

Tests cover:
- Supervisor API endpoints
- Worker status endpoint returns correct data
- Worker reset endpoint works correctly
- End-to-end supervisor lifecycle
- Prometheus metrics recording
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from backend.api.routes.system import register_workers
from backend.services.worker_supervisor import (
    SupervisorConfig,
    WorkerStatus,
    WorkerSupervisor,
    reset_worker_supervisor,
)

pytestmark = pytest.mark.asyncio


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def supervisor_config() -> SupervisorConfig:
    """Create test configuration with short intervals."""
    return SupervisorConfig(
        check_interval=0.1,
        default_max_restarts=3,
        default_backoff_base=0.05,
        default_backoff_max=0.5,
    )


@pytest.fixture
def mock_broadcaster() -> AsyncMock:
    """Create a mock EventBroadcaster."""
    broadcaster = AsyncMock()
    broadcaster.broadcast_service_status = AsyncMock()
    return broadcaster


@pytest.fixture
async def supervisor(
    supervisor_config: SupervisorConfig,
    mock_broadcaster: AsyncMock,
) -> WorkerSupervisor:
    """Create a WorkerSupervisor instance for testing."""
    reset_worker_supervisor()
    supervisor = WorkerSupervisor(config=supervisor_config, broadcaster=mock_broadcaster)
    yield supervisor
    await supervisor.stop()
    reset_worker_supervisor()


@pytest.fixture(autouse=True)
async def reset_globals():
    """Reset global state before and after each test."""
    reset_worker_supervisor()
    # Clear registered workers in system routes
    register_workers()
    yield
    reset_worker_supervisor()
    register_workers()


# ============================================================================
# Supervisor API Endpoint Tests
# ============================================================================


class TestSupervisorAPIEndpoints:
    """Tests for supervisor status API endpoints."""

    async def test_supervisor_status_endpoint_no_supervisor(self, client) -> None:
        """Test supervisor status endpoint when supervisor is not initialized."""
        response = await client.get("/api/system/supervisor")
        assert response.status_code == 200

        data = response.json()
        assert data["running"] is False
        assert data["worker_count"] == 0
        assert data["workers"] == []
        assert "timestamp" in data

    async def test_supervisor_status_endpoint_with_workers(
        self,
        client,
        supervisor: WorkerSupervisor,
    ) -> None:
        """Test supervisor status endpoint with registered workers."""

        # Register test workers
        async def test_worker() -> None:
            await asyncio.sleep(10)  # cancelled by supervisor.stop()

        await supervisor.register_worker("test_worker_1", test_worker)
        await supervisor.register_worker("test_worker_2", test_worker)

        # Register supervisor with system routes
        register_workers(worker_supervisor=supervisor)

        # Start supervisor
        await supervisor.start()

        # Wait for workers to start
        await asyncio.sleep(0.2)

        response = await client.get("/api/system/supervisor")
        assert response.status_code == 200

        data = response.json()
        assert data["running"] is True
        assert data["worker_count"] == 2
        assert len(data["workers"]) == 2

        # Check worker info structure
        worker_names = {w["name"] for w in data["workers"]}
        assert "test_worker_1" in worker_names
        assert "test_worker_2" in worker_names

        for worker in data["workers"]:
            assert "name" in worker
            assert "status" in worker
            assert "restart_count" in worker
            assert "max_restarts" in worker

    async def test_reset_worker_endpoint_success(
        self,
        client,
        supervisor: WorkerSupervisor,
    ) -> None:
        """Test worker reset endpoint for a failed worker."""

        # Register a worker
        async def test_worker() -> None:
            await asyncio.sleep(10)  # cancelled by supervisor.stop()

        await supervisor.register_worker("test_worker", test_worker)

        # Manually set to failed state
        supervisor._workers["test_worker"].status = WorkerStatus.FAILED
        supervisor._workers["test_worker"].restart_count = 5

        # Register supervisor with system routes
        register_workers(worker_supervisor=supervisor)

        response = await client.post("/api/system/supervisor/reset/test_worker")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert "reset" in data["message"].lower()

        # Verify worker was reset
        info = supervisor.get_worker_info("test_worker")
        assert info is not None
        assert info.restart_count == 0
        assert info.status == WorkerStatus.STOPPED

    async def test_reset_worker_endpoint_not_found(
        self,
        client,
        supervisor: WorkerSupervisor,
    ) -> None:
        """Test worker reset endpoint for non-existent worker."""
        # Register supervisor with system routes (no workers registered)
        register_workers(worker_supervisor=supervisor)

        response = await client.post("/api/system/supervisor/reset/unknown_worker")
        assert response.status_code == 404

        data = response.json()
        assert "not found" in data["detail"].lower()

    async def test_reset_worker_endpoint_no_supervisor(self, client) -> None:
        """Test worker reset endpoint when supervisor is not initialized."""
        response = await client.post("/api/system/supervisor/reset/test_worker")
        assert response.status_code == 503

        data = response.json()
        assert "not initialized" in data["detail"].lower()


# ============================================================================
# Worker Crash and Recovery Integration Tests
# ============================================================================


class TestWorkerCrashRecovery:
    """Integration tests for worker crash detection and recovery."""

    async def test_worker_crash_and_restart(
        self,
        supervisor: WorkerSupervisor,
    ) -> None:
        """Test that crashed worker is automatically restarted."""
        call_count = 0
        restarted = asyncio.Event()

        async def flaky_worker() -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("First crash")
            restarted.set()
            await asyncio.sleep(10)  # cancelled by supervisor.stop()

        await supervisor.register_worker("flaky_worker", flaky_worker)
        await supervisor.start()

        # Wait for restart
        await asyncio.wait_for(restarted.wait(), timeout=2.0)

        info = supervisor.get_worker_info("flaky_worker")
        assert info is not None
        assert info.restart_count >= 1
        assert info.status == WorkerStatus.RUNNING

    async def test_worker_exceeds_max_restarts(
        self,
        supervisor: WorkerSupervisor,
    ) -> None:
        """Test worker enters FAILED state after max restarts exceeded."""

        async def always_crashes() -> None:
            raise RuntimeError("Always fails")

        await supervisor.register_worker(
            "always_crashes",
            always_crashes,
            max_restarts=2,
        )
        await supervisor.start()

        # Wait for all restarts to be exhausted
        await asyncio.sleep(1.0)  # cancelled after test completes

        info = supervisor.get_worker_info("always_crashes")
        assert info is not None
        assert info.status == WorkerStatus.FAILED
        assert info.restart_count >= 2


# ============================================================================
# Prometheus Metrics Integration Tests
# ============================================================================


class TestPrometheusMetrics:
    """Integration tests for Prometheus metrics recording."""

    async def test_worker_restart_metrics_recorded(
        self,
        supervisor: WorkerSupervisor,
    ) -> None:
        """Test that worker restart metrics are recorded (NEM-4148)."""
        from backend.core.metrics import WORKER_RESTARTS_TOTAL

        call_count = 0
        restarted = asyncio.Event()

        async def flaky_worker() -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("First crash")
            restarted.set()
            await asyncio.sleep(10)  # cancelled by supervisor.stop()

        await supervisor.register_worker("metrics_test_worker", flaky_worker)

        # Get initial metric value (NEM-4148: now requires worker_type and reason labels)
        # The worker_type is auto-detected as "unknown" (no special keywords in name)
        # The reason is auto-categorized as "crash" (error contains "crash")
        initial_value = WORKER_RESTARTS_TOTAL.labels(
            worker_name="metrics_test_worker",
            worker_type="unknown",
            reason="crash",
        )._value.get()

        await supervisor.start()
        await asyncio.wait_for(restarted.wait(), timeout=2.0)

        # Check metric was incremented
        final_value = WORKER_RESTARTS_TOTAL.labels(
            worker_name="metrics_test_worker",
            worker_type="unknown",
            reason="crash",
        )._value.get()
        assert final_value > initial_value

    async def test_worker_crash_metrics_recorded(
        self,
        supervisor: WorkerSupervisor,
    ) -> None:
        """Test that worker crash metrics are recorded (NEM-4148)."""
        from backend.core.metrics import WORKER_CRASHES_TOTAL

        crashed = asyncio.Event()

        async def crashing_worker() -> None:
            crashed.set()
            raise RuntimeError("Test crash")

        await supervisor.register_worker(
            "crash_metrics_worker",
            crashing_worker,
            max_restarts=0,  # Don't restart
        )

        # Get initial metric value (NEM-4148: now requires worker_type and exit_code labels)
        # The worker_type is auto-detected as "unknown" (no special keywords in name)
        # The exit_code is auto-extracted as "unknown" (no exit code in error message)
        initial_value = WORKER_CRASHES_TOTAL.labels(
            worker_name="crash_metrics_worker",
            worker_type="unknown",
            exit_code="unknown",
        )._value.get()

        await supervisor.start()
        await asyncio.sleep(0.3)

        # Check metric was incremented
        final_value = WORKER_CRASHES_TOTAL.labels(
            worker_name="crash_metrics_worker",
            worker_type="unknown",
            exit_code="unknown",
        )._value.get()
        assert final_value > initial_value


# ============================================================================
# End-to-End Supervisor Lifecycle Tests
# ============================================================================


class TestSupervisorLifecycle:
    """Integration tests for supervisor lifecycle."""

    async def test_full_lifecycle(
        self,
        supervisor: WorkerSupervisor,
    ) -> None:
        """Test complete supervisor lifecycle: start -> run -> stop."""
        started = asyncio.Event()

        async def worker() -> None:
            started.set()
            await asyncio.sleep(10)  # cancelled by supervisor.stop()

        await supervisor.register_worker("lifecycle_worker", worker)

        # Start
        await supervisor.start()
        await asyncio.wait_for(started.wait(), timeout=1.0)

        assert supervisor.is_running
        assert supervisor.get_worker_status("lifecycle_worker") == WorkerStatus.RUNNING

        # Stop
        await supervisor.stop()

        assert not supervisor.is_running
        assert supervisor.get_worker_status("lifecycle_worker") == WorkerStatus.STOPPED

    async def test_concurrent_worker_operations(
        self,
        supervisor: WorkerSupervisor,
    ) -> None:
        """Test supervisor handles concurrent worker operations correctly."""
        events = {f"worker_{i}": asyncio.Event() for i in range(3)}

        async def make_worker(idx: int):
            async def worker() -> None:
                events[f"worker_{idx}"].set()
                await asyncio.sleep(10)  # cancelled by supervisor.stop()

            return worker

        # Register multiple workers
        for i in range(3):
            worker = await make_worker(i)
            await supervisor.register_worker(f"worker_{i}", worker)

        await supervisor.start()

        # Wait for all workers to start
        await asyncio.gather(
            *[asyncio.wait_for(events[f"worker_{i}"].wait(), timeout=1.0) for i in range(3)]
        )

        assert supervisor.worker_count == 3

        # All workers should be running
        for i in range(3):
            status = supervisor.get_worker_status(f"worker_{i}")
            assert status == WorkerStatus.RUNNING
