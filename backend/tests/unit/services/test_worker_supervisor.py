"""Unit tests for WorkerSupervisor service.

Tests cover:
- Worker registration and unregistration
- Supervisor start/stop lifecycle
- Worker crash detection and restart
- Exponential backoff calculation
- Max restart limit enforcement
- Status broadcasting
- Thread-safe restart handling
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from backend.services.worker_supervisor import (
    SupervisorConfig,
    WorkerInfo,
    WorkerStatus,
    WorkerSupervisor,
    get_worker_supervisor,
    reset_worker_supervisor,
)

pytestmark = pytest.mark.unit


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def supervisor_config() -> SupervisorConfig:
    """Create a test configuration with short intervals."""
    return SupervisorConfig(
        check_interval=0.1,  # Fast for tests
        default_max_restarts=3,
        default_backoff_base=0.1,  # Fast for tests
        default_backoff_max=1.0,
    )


@pytest.fixture
def mock_broadcaster() -> AsyncMock:
    """Create a mock EventBroadcaster."""
    broadcaster = AsyncMock()
    broadcaster.broadcast_service_status = AsyncMock()
    return broadcaster


@pytest.fixture
def supervisor(
    supervisor_config: SupervisorConfig,
    mock_broadcaster: AsyncMock,
) -> WorkerSupervisor:
    """Create a WorkerSupervisor instance for testing."""
    reset_worker_supervisor()
    return WorkerSupervisor(config=supervisor_config, broadcaster=mock_broadcaster)


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the singleton before and after each test."""
    reset_worker_supervisor()
    yield
    reset_worker_supervisor()


# ============================================================================
# Worker Registration Tests
# ============================================================================


class TestWorkerRegistration:
    """Tests for worker registration and unregistration."""

    async def test_register_worker_success(self, supervisor: WorkerSupervisor) -> None:
        """Test successful worker registration."""

        async def worker() -> None:
            pass

        await supervisor.register_worker("test_worker", worker)

        assert "test_worker" in supervisor._workers
        assert supervisor.worker_count == 1

        info = supervisor.get_worker_info("test_worker")
        assert info is not None
        assert info.name == "test_worker"
        assert info.status == WorkerStatus.STOPPED

    async def test_register_duplicate_worker_raises(self, supervisor: WorkerSupervisor) -> None:
        """Test that registering duplicate worker raises ValueError."""

        async def worker() -> None:
            pass

        await supervisor.register_worker("test_worker", worker)

        with pytest.raises(ValueError, match="already registered"):
            await supervisor.register_worker("test_worker", worker)

    async def test_register_worker_custom_config(self, supervisor: WorkerSupervisor) -> None:
        """Test registering worker with custom configuration."""

        async def worker() -> None:
            pass

        await supervisor.register_worker(
            "test_worker",
            worker,
            max_restarts=10,
            backoff_base=2.0,
            backoff_max=120.0,
        )

        info = supervisor.get_worker_info("test_worker")
        assert info is not None
        assert info.max_restarts == 10
        assert info.backoff_base == 2.0
        assert info.backoff_max == 120.0

    async def test_unregister_worker_success(self, supervisor: WorkerSupervisor) -> None:
        """Test successful worker unregistration."""

        async def worker() -> None:
            pass

        await supervisor.register_worker("test_worker", worker)
        await supervisor.unregister_worker("test_worker")

        assert "test_worker" not in supervisor._workers
        assert supervisor.worker_count == 0

    async def test_unregister_unknown_worker(self, supervisor: WorkerSupervisor) -> None:
        """Test unregistering unknown worker logs warning but doesn't raise."""
        # Should not raise
        await supervisor.unregister_worker("unknown_worker")


# ============================================================================
# Supervisor Lifecycle Tests
# ============================================================================


class TestSupervisorLifecycle:
    """Tests for supervisor start and stop."""

    async def test_start_supervisor(self, supervisor: WorkerSupervisor) -> None:
        """Test starting the supervisor."""
        started = asyncio.Event()

        async def worker() -> None:
            started.set()
            await asyncio.sleep(10)  # cancelled by supervisor.stop()

        await supervisor.register_worker("test_worker", worker)
        await supervisor.start()

        try:
            # Wait for worker to start
            await asyncio.wait_for(started.wait(), timeout=1.0)

            assert supervisor.is_running
            assert supervisor.get_worker_status("test_worker") == WorkerStatus.RUNNING
        finally:
            await supervisor.stop()

    async def test_stop_supervisor(self, supervisor: WorkerSupervisor) -> None:
        """Test stopping the supervisor."""

        async def worker() -> None:
            await asyncio.sleep(10)  # cancelled by supervisor.stop()

        await supervisor.register_worker("test_worker", worker)
        await supervisor.start()
        await supervisor.stop()

        assert not supervisor.is_running
        assert supervisor.get_worker_status("test_worker") == WorkerStatus.STOPPED

    async def test_start_already_running(self, supervisor: WorkerSupervisor) -> None:
        """Test that starting when already running logs warning."""

        async def worker() -> None:
            await asyncio.sleep(10)  # cancelled by supervisor.stop()

        await supervisor.register_worker("test_worker", worker)
        await supervisor.start()

        try:
            # Should not raise, just log warning
            await supervisor.start()
            assert supervisor.is_running
        finally:
            await supervisor.stop()

    async def test_stop_not_running(self, supervisor: WorkerSupervisor) -> None:
        """Test stopping when not running is safe."""
        # Should not raise
        await supervisor.stop()
        assert not supervisor.is_running


# ============================================================================
# Worker Crash and Restart Tests
# ============================================================================


class TestWorkerCrashRestart:
    """Tests for worker crash detection and restart."""

    async def test_worker_crash_detected(
        self,
        supervisor: WorkerSupervisor,
        mock_broadcaster: AsyncMock,
    ) -> None:
        """Test that worker crashes are detected."""
        crash_count = 0

        async def crashing_worker() -> None:
            nonlocal crash_count
            crash_count += 1
            raise RuntimeError("Test crash")

        await supervisor.register_worker("crashing_worker", crashing_worker)
        await supervisor.start()

        try:
            # Wait for crash detection
            await asyncio.sleep(0.3)

            info = supervisor.get_worker_info("crashing_worker")
            assert info is not None
            assert info.error == "Test crash"
            assert info.last_crashed_at is not None
        finally:
            await supervisor.stop()

    async def test_worker_auto_restart(
        self,
        supervisor: WorkerSupervisor,
    ) -> None:
        """Test that crashed workers are auto-restarted."""
        call_count = 0
        started = asyncio.Event()

        async def flaky_worker() -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("First crash")
            started.set()
            await asyncio.sleep(10)  # cancelled by supervisor.stop()

        await supervisor.register_worker("flaky_worker", flaky_worker)
        await supervisor.start()

        try:
            # Wait for restart
            await asyncio.wait_for(started.wait(), timeout=2.0)

            info = supervisor.get_worker_info("flaky_worker")
            assert info is not None
            assert info.restart_count == 1
            assert info.status == WorkerStatus.RUNNING
        finally:
            await supervisor.stop()

    async def test_max_restarts_exceeded(
        self,
        supervisor: WorkerSupervisor,
    ) -> None:
        """Test that workers stop restarting after max_restarts."""

        async def always_crashes() -> None:
            raise RuntimeError("Always fails")

        await supervisor.register_worker(
            "always_crashes",
            always_crashes,
            max_restarts=2,
            backoff_base=0.05,
        )
        await supervisor.start()

        try:
            # Wait for all restart attempts - short wait since backoff_base=0.05
            await asyncio.sleep(1.0)  # intentionally short for test

            info = supervisor.get_worker_info("always_crashes")
            assert info is not None
            assert info.status == WorkerStatus.FAILED
            assert info.restart_count >= 2
        finally:
            await supervisor.stop()


# ============================================================================
# Backoff Calculation Tests
# ============================================================================


class TestBackoffCalculation:
    """Tests for exponential backoff calculation."""

    def test_backoff_first_restart(self, supervisor: WorkerSupervisor) -> None:
        """Test backoff for first restart."""
        worker = WorkerInfo(
            name="test",
            factory=AsyncMock(),
            restart_count=0,
            backoff_base=1.0,
            backoff_max=60.0,
        )

        backoff = supervisor._calculate_backoff(worker)
        assert backoff == 1.0  # 1.0 * 2^0 = 1.0

    def test_backoff_exponential_growth(self, supervisor: WorkerSupervisor) -> None:
        """Test exponential backoff growth."""
        worker = WorkerInfo(
            name="test",
            factory=AsyncMock(),
            restart_count=3,
            backoff_base=1.0,
            backoff_max=60.0,
        )

        backoff = supervisor._calculate_backoff(worker)
        assert backoff == 8.0  # 1.0 * 2^3 = 8.0

    def test_backoff_capped_at_max(self, supervisor: WorkerSupervisor) -> None:
        """Test backoff is capped at max value."""
        worker = WorkerInfo(
            name="test",
            factory=AsyncMock(),
            restart_count=10,
            backoff_base=1.0,
            backoff_max=60.0,
        )

        backoff = supervisor._calculate_backoff(worker)
        assert backoff == 60.0  # Capped at max


# ============================================================================
# Status Broadcast Tests
# ============================================================================


class TestStatusBroadcast:
    """Tests for status broadcasting."""

    async def test_broadcast_on_start(
        self,
        supervisor: WorkerSupervisor,
        mock_broadcaster: AsyncMock,
    ) -> None:
        """Test that status is broadcast when worker starts."""

        async def worker() -> None:
            await asyncio.sleep(10)  # cancelled by supervisor.stop()

        await supervisor.register_worker("test_worker", worker)
        await supervisor.start()

        try:
            await asyncio.sleep(0.1)

            mock_broadcaster.broadcast_service_status.assert_called()
            call_args = mock_broadcaster.broadcast_service_status.call_args[0][0]
            assert call_args["data"]["service"] == "worker:test_worker"
            assert call_args["data"]["status"] == "running"
        finally:
            await supervisor.stop()

    async def test_broadcast_on_crash(
        self,
        supervisor: WorkerSupervisor,
        mock_broadcaster: AsyncMock,
    ) -> None:
        """Test that status is broadcast when worker crashes."""

        async def crashing_worker() -> None:
            raise RuntimeError("Test crash")

        await supervisor.register_worker(
            "crashing_worker",
            crashing_worker,
            max_restarts=0,  # Don't restart
        )
        await supervisor.start()

        try:
            await asyncio.sleep(0.3)

            # Check that crash was broadcast
            calls = mock_broadcaster.broadcast_service_status.call_args_list
            crash_calls = [c for c in calls if c[0][0]["data"]["status"] == "crashed"]
            assert len(crash_calls) > 0
        finally:
            await supervisor.stop()

    async def test_broadcast_failure_handled(
        self,
        supervisor: WorkerSupervisor,
        mock_broadcaster: AsyncMock,
    ) -> None:
        """Test that broadcast failures don't crash the supervisor."""
        mock_broadcaster.broadcast_service_status.side_effect = Exception("Broadcast failed")

        async def worker() -> None:
            await asyncio.sleep(10)  # cancelled by supervisor.stop()

        await supervisor.register_worker("test_worker", worker)
        await supervisor.start()

        try:
            await asyncio.sleep(0.1)
            # Should not crash despite broadcast failure
            assert supervisor.is_running
        finally:
            await supervisor.stop()


# ============================================================================
# Worker Status Query Tests
# ============================================================================


class TestWorkerStatusQuery:
    """Tests for querying worker status."""

    async def test_get_worker_status(self, supervisor: WorkerSupervisor) -> None:
        """Test getting worker status."""

        async def worker() -> None:
            pass

        await supervisor.register_worker("test_worker", worker)

        status = supervisor.get_worker_status("test_worker")
        assert status == WorkerStatus.STOPPED

    async def test_get_unknown_worker_status(self, supervisor: WorkerSupervisor) -> None:
        """Test getting status of unknown worker returns None."""
        status = supervisor.get_worker_status("unknown")
        assert status is None

    async def test_get_all_workers(self, supervisor: WorkerSupervisor) -> None:
        """Test getting all workers."""

        async def worker1() -> None:
            pass

        async def worker2() -> None:
            pass

        await supervisor.register_worker("worker1", worker1)
        await supervisor.register_worker("worker2", worker2)

        all_workers = supervisor.get_all_workers()
        assert len(all_workers) == 2
        assert "worker1" in all_workers
        assert "worker2" in all_workers


# ============================================================================
# Reset Worker Tests
# ============================================================================


class TestResetWorker:
    """Tests for resetting failed workers."""

    async def test_reset_worker(self, supervisor: WorkerSupervisor) -> None:
        """Test resetting a worker's restart count."""

        async def worker() -> None:
            pass

        await supervisor.register_worker("test_worker", worker)

        # Manually set to failed state
        supervisor._workers["test_worker"].restart_count = 5
        supervisor._workers["test_worker"].status = WorkerStatus.FAILED

        result = supervisor.reset_worker("test_worker")

        assert result is True
        info = supervisor.get_worker_info("test_worker")
        assert info is not None
        assert info.restart_count == 0
        assert info.status == WorkerStatus.STOPPED

    async def test_reset_unknown_worker(self, supervisor: WorkerSupervisor) -> None:
        """Test resetting unknown worker returns False."""
        result = supervisor.reset_worker("unknown")
        assert result is False


# ============================================================================
# Singleton Tests
# ============================================================================


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_worker_supervisor_creates_instance(self) -> None:
        """Test that get_worker_supervisor creates instance."""
        reset_worker_supervisor()

        supervisor = get_worker_supervisor()
        assert supervisor is not None
        assert isinstance(supervisor, WorkerSupervisor)

    def test_get_worker_supervisor_returns_same_instance(self) -> None:
        """Test that get_worker_supervisor returns same instance."""
        reset_worker_supervisor()

        supervisor1 = get_worker_supervisor()
        supervisor2 = get_worker_supervisor()
        assert supervisor1 is supervisor2

    def test_reset_worker_supervisor(self) -> None:
        """Test that reset clears the singleton."""
        supervisor1 = get_worker_supervisor()
        reset_worker_supervisor()
        supervisor2 = get_worker_supervisor()

        assert supervisor1 is not supervisor2
