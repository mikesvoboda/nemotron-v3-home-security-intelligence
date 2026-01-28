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
    RestartPolicy,
    SupervisorConfig,
    WorkerConfig,
    WorkerInfo,
    WorkerState,
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


# ============================================================================
# NEM-2492: WorkerState Enum Tests
# ============================================================================


class TestWorkerStateEnum:
    """Tests for WorkerState enum (NEM-2492)."""

    def test_worker_state_values(self) -> None:
        """Test that WorkerState has all expected values."""
        assert WorkerState.IDLE.value == "idle"
        assert WorkerState.RUNNING.value == "running"
        assert WorkerState.RESTARTING.value == "restarting"
        assert WorkerState.FAILED.value == "failed"
        assert WorkerState.STOPPED.value == "stopped"

    def test_worker_state_members(self) -> None:
        """Test that WorkerState has exactly 5 members."""
        assert len(WorkerState) == 5

    def test_worker_state_from_value(self) -> None:
        """Test creating WorkerState from string value."""
        assert WorkerState("idle") == WorkerState.IDLE
        assert WorkerState("running") == WorkerState.RUNNING
        assert WorkerState("restarting") == WorkerState.RESTARTING
        assert WorkerState("failed") == WorkerState.FAILED
        assert WorkerState("stopped") == WorkerState.STOPPED


# ============================================================================
# NEM-2492: RestartPolicy Enum Tests
# ============================================================================


class TestRestartPolicyEnum:
    """Tests for RestartPolicy enum (NEM-2492)."""

    def test_restart_policy_values(self) -> None:
        """Test that RestartPolicy has all expected values."""
        assert RestartPolicy.ALWAYS.value == "always"
        assert RestartPolicy.ON_FAILURE.value == "on_failure"
        assert RestartPolicy.NEVER.value == "never"

    def test_restart_policy_members(self) -> None:
        """Test that RestartPolicy has exactly 3 members."""
        assert len(RestartPolicy) == 3

    def test_restart_policy_from_value(self) -> None:
        """Test creating RestartPolicy from string value."""
        assert RestartPolicy("always") == RestartPolicy.ALWAYS
        assert RestartPolicy("on_failure") == RestartPolicy.ON_FAILURE
        assert RestartPolicy("never") == RestartPolicy.NEVER


# ============================================================================
# NEM-2492: WorkerConfig Dataclass Tests
# ============================================================================


class TestWorkerConfigDataclass:
    """Tests for WorkerConfig dataclass (NEM-2492)."""

    def test_worker_config_defaults(self) -> None:
        """Test WorkerConfig default values."""

        async def factory() -> None:
            pass

        config = WorkerConfig(name="test", coroutine_factory=factory)
        assert config.name == "test"
        assert config.coroutine_factory is factory
        assert config.restart_policy == RestartPolicy.ON_FAILURE
        assert config.max_restarts == 5
        assert config.restart_delay_base == 1.0
        assert config.health_check_interval == 30.0

    def test_worker_config_custom_values(self) -> None:
        """Test WorkerConfig with custom values."""

        async def factory() -> None:
            pass

        config = WorkerConfig(
            name="custom",
            coroutine_factory=factory,
            restart_policy=RestartPolicy.ALWAYS,
            max_restarts=10,
            restart_delay_base=2.0,
            health_check_interval=60.0,
        )
        assert config.name == "custom"
        assert config.restart_policy == RestartPolicy.ALWAYS
        assert config.max_restarts == 10
        assert config.restart_delay_base == 2.0
        assert config.health_check_interval == 60.0


# ============================================================================
# NEM-2492: WorkerInfo to_dict and circuit_open Tests
# ============================================================================


class TestWorkerInfoDataclass:
    """Tests for WorkerInfo dataclass additions (NEM-2492)."""

    def test_circuit_open_default(self) -> None:
        """Test that circuit_open defaults to False."""
        worker = WorkerInfo(
            name="test",
            factory=AsyncMock(),
            restart_count=0,
            backoff_base=1.0,
            backoff_max=60.0,
        )
        assert worker.circuit_open is False

    def test_circuit_open_can_be_set(self) -> None:
        """Test that circuit_open can be set to True."""
        worker = WorkerInfo(
            name="test",
            factory=AsyncMock(),
            restart_count=0,
            backoff_base=1.0,
            backoff_max=60.0,
            circuit_open=True,
        )
        assert worker.circuit_open is True

    def test_to_dict_returns_dict(self) -> None:
        """Test that to_dict returns a dictionary."""
        worker = WorkerInfo(
            name="test",
            factory=AsyncMock(),
            restart_count=0,
            backoff_base=1.0,
            backoff_max=60.0,
        )
        result = worker.to_dict()
        assert isinstance(result, dict)

    def test_to_dict_contains_all_fields(self) -> None:
        """Test that to_dict contains all expected fields."""
        worker = WorkerInfo(
            name="test",
            factory=AsyncMock(),
            restart_count=3,
            backoff_base=1.0,
            backoff_max=60.0,
            circuit_open=True,
        )
        result = worker.to_dict()

        assert result["name"] == "test"
        assert result["status"] == WorkerStatus.STOPPED.value
        assert result["restart_count"] == 3
        assert result["max_restarts"] == 5  # default
        assert result["backoff_base"] == 1.0
        assert result["backoff_max"] == 60.0
        assert result["last_started_at"] is None
        assert result["last_crashed_at"] is None
        assert result["error"] is None
        assert result["circuit_open"] is True
        # NEM-4148: Heartbeat fields
        assert result["last_heartbeat_at"] is None
        assert result["heartbeat_timeout"] == 30.0  # default
        assert result["missed_heartbeat_count"] == 0  # default


# ============================================================================
# NEM-2492: Circuit Breaker Tests
# ============================================================================


class TestCircuitBreaker:
    """Tests for circuit breaker functionality (NEM-2492)."""

    async def test_circuit_opens_after_max_restarts(
        self,
        supervisor: WorkerSupervisor,
    ) -> None:
        """Test that circuit breaker opens after max restarts exceeded."""

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
            assert info.circuit_open is True
            assert info.status == WorkerStatus.FAILED
        finally:
            await supervisor.stop()

    async def test_reset_circuit_breaker_success(
        self,
        supervisor: WorkerSupervisor,
    ) -> None:
        """Test resetting circuit breaker for a failed worker."""

        async def worker() -> None:
            pass

        await supervisor.register_worker("test_worker", worker)

        # Manually set to failed state with open circuit
        supervisor._workers["test_worker"].circuit_open = True
        supervisor._workers["test_worker"].restart_count = 5
        supervisor._workers["test_worker"].status = WorkerStatus.FAILED

        result = supervisor.reset_circuit_breaker("test_worker")

        assert result is True
        info = supervisor.get_worker_info("test_worker")
        assert info is not None
        assert info.circuit_open is False
        assert info.restart_count == 0
        assert info.status == WorkerStatus.STOPPED

    async def test_reset_circuit_breaker_unknown_worker(
        self,
        supervisor: WorkerSupervisor,
    ) -> None:
        """Test resetting circuit breaker for unknown worker returns False."""
        result = supervisor.reset_circuit_breaker("unknown")
        assert result is False


# ============================================================================
# NEM-2492: get_all_statuses Tests
# ============================================================================


class TestGetAllStatuses:
    """Tests for get_all_statuses method (NEM-2492)."""

    async def test_get_all_statuses_empty(self, supervisor: WorkerSupervisor) -> None:
        """Test get_all_statuses with no workers."""
        statuses = supervisor.get_all_statuses()
        assert statuses == {}

    async def test_get_all_statuses_single_worker(
        self,
        supervisor: WorkerSupervisor,
    ) -> None:
        """Test get_all_statuses with a single worker."""

        async def worker() -> None:
            pass

        await supervisor.register_worker("test_worker", worker)
        statuses = supervisor.get_all_statuses()

        assert len(statuses) == 1
        assert "test_worker" in statuses
        assert statuses["test_worker"]["name"] == "test_worker"
        assert statuses["test_worker"]["status"] == WorkerStatus.STOPPED.value

    async def test_get_all_statuses_multiple_workers(
        self,
        supervisor: WorkerSupervisor,
    ) -> None:
        """Test get_all_statuses with multiple workers."""

        async def worker1() -> None:
            pass

        async def worker2() -> None:
            pass

        await supervisor.register_worker("worker1", worker1)
        await supervisor.register_worker("worker2", worker2)

        statuses = supervisor.get_all_statuses()

        assert len(statuses) == 2
        assert "worker1" in statuses
        assert "worker2" in statuses


# ============================================================================
# NEM-2492: _calculate_backoff_static Tests
# ============================================================================


class TestCalculateBackoffStatic:
    """Tests for _calculate_backoff_static static method (NEM-2492)."""

    def test_backoff_zero_restarts(self) -> None:
        """Test backoff with zero restarts returns base."""
        result = WorkerSupervisor._calculate_backoff_static(0, 1.0, 60.0)
        assert result == 1.0

    def test_backoff_first_restart(self) -> None:
        """Test backoff for first restart."""
        result = WorkerSupervisor._calculate_backoff_static(1, 1.0, 60.0)
        assert result == 1.0  # 1.0 * 2^0 = 1.0

    def test_backoff_exponential_growth(self) -> None:
        """Test exponential backoff growth."""
        result = WorkerSupervisor._calculate_backoff_static(3, 1.0, 60.0)
        assert result == 4.0  # 1.0 * 2^2 = 4.0

    def test_backoff_capped_at_max(self) -> None:
        """Test backoff is capped at max value."""
        result = WorkerSupervisor._calculate_backoff_static(10, 1.0, 60.0)
        assert result == 60.0  # Capped at max

    def test_backoff_custom_base(self) -> None:
        """Test backoff with custom base value."""
        result = WorkerSupervisor._calculate_backoff_static(2, 2.0, 60.0)
        assert result == 4.0  # 2.0 * 2^1 = 4.0

    def test_backoff_returns_float(self) -> None:
        """Test that backoff always returns a float."""
        result = WorkerSupervisor._calculate_backoff_static(3, 1.0, 60.0)
        assert isinstance(result, float)


# ============================================================================
# Restart History Tests (NEM-2462)
# ============================================================================


class TestRestartHistory:
    """Tests for restart history tracking (NEM-2462)."""

    async def test_get_restart_history_empty(self, supervisor: WorkerSupervisor) -> None:
        """Test get_restart_history returns empty list initially."""
        history = supervisor.get_restart_history()
        assert history == []

    async def test_get_restart_history_after_restart(
        self,
        supervisor: WorkerSupervisor,
    ) -> None:
        """Test restart events are recorded in history."""
        call_count = 0

        async def flaky_worker() -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("First crash")
            await asyncio.sleep(10)  # cancelled

        await supervisor.register_worker(
            "flaky_worker",
            flaky_worker,
            backoff_base=0.05,
        )
        await supervisor.start()

        try:
            # Wait for restart
            await asyncio.sleep(0.5)

            history = supervisor.get_restart_history()
            assert len(history) >= 1

            # Check event structure
            event = history[0]
            assert event["worker_name"] == "flaky_worker"
            assert event["status"] == "success"
            assert event["attempt"] >= 1
            assert "timestamp" in event
        finally:
            await supervisor.stop()

    async def test_get_restart_history_filter_by_worker(
        self,
        supervisor: WorkerSupervisor,
    ) -> None:
        """Test filtering restart history by worker name."""

        async def crashing_worker1() -> None:
            raise RuntimeError("Crash 1")

        async def crashing_worker2() -> None:
            raise RuntimeError("Crash 2")

        await supervisor.register_worker(
            "worker1",
            crashing_worker1,
            max_restarts=1,
            backoff_base=0.05,
        )
        await supervisor.register_worker(
            "worker2",
            crashing_worker2,
            max_restarts=1,
            backoff_base=0.05,
        )
        await supervisor.start()

        try:
            # Wait for restarts
            await asyncio.sleep(0.5)

            # Get history for worker1 only
            history = supervisor.get_restart_history(worker_name="worker1")
            assert all(e["worker_name"] == "worker1" for e in history)
        finally:
            await supervisor.stop()

    async def test_get_restart_history_pagination(
        self,
        supervisor: WorkerSupervisor,
    ) -> None:
        """Test restart history pagination."""
        # Manually add events
        for i in range(10):
            supervisor._record_restart_event(
                worker_name="test",
                attempt=i,
                status="success",
                error=None,
            )

        # Test limit
        history = supervisor.get_restart_history(limit=5)
        assert len(history) == 5

        # Test offset
        history = supervisor.get_restart_history(offset=5, limit=5)
        assert len(history) == 5

    async def test_get_restart_history_count(
        self,
        supervisor: WorkerSupervisor,
    ) -> None:
        """Test getting restart history count."""
        assert supervisor.get_restart_history_count() == 0

        # Add some events
        for i in range(5):
            supervisor._record_restart_event(
                worker_name="test",
                attempt=i,
                status="success",
                error=None,
            )

        assert supervisor.get_restart_history_count() == 5
        assert supervisor.get_restart_history_count(worker_name="test") == 5
        assert supervisor.get_restart_history_count(worker_name="other") == 0

    async def test_restart_history_max_size(
        self,
        supervisor_config: SupervisorConfig,
        mock_broadcaster: AsyncMock,
    ) -> None:
        """Test restart history is trimmed to max size."""
        config = SupervisorConfig(
            check_interval=0.1,
            max_restart_history=10,
        )
        supervisor = WorkerSupervisor(config=config, broadcaster=mock_broadcaster)

        # Add more than max
        for i in range(15):
            supervisor._record_restart_event(
                worker_name="test",
                attempt=i,
                status="success",
                error=None,
            )

        # Should be trimmed to max
        assert len(supervisor._restart_history) == 10

    async def test_restart_history_newest_first(
        self,
        supervisor: WorkerSupervisor,
    ) -> None:
        """Test restart history is returned newest first."""
        # Add events over time
        for i in range(3):
            supervisor._record_restart_event(
                worker_name="test",
                attempt=i,
                status="success",
                error=None,
            )
            await asyncio.sleep(0.01)  # Ensure different timestamps

        history = supervisor.get_restart_history()
        assert len(history) == 3

        # Should be newest first
        assert history[0]["attempt"] == 2
        assert history[1]["attempt"] == 1
        assert history[2]["attempt"] == 0


# ============================================================================
# Manual Worker Control Tests (NEM-2462)
# ============================================================================


class TestManualWorkerControl:
    """Tests for manual worker control methods (NEM-2462)."""

    async def test_start_worker_manually(
        self,
        supervisor: WorkerSupervisor,
    ) -> None:
        """Test manually starting a stopped worker."""
        started = asyncio.Event()

        async def worker() -> None:
            started.set()
            await asyncio.sleep(10)  # cancelled

        await supervisor.register_worker("test_worker", worker)

        # Start manually (supervisor not started)
        result = await supervisor.start_worker("test_worker")
        assert result is True

        try:
            await asyncio.wait_for(started.wait(), timeout=1.0)
            assert supervisor.get_worker_status("test_worker") == WorkerStatus.RUNNING
        finally:
            await supervisor.stop_worker("test_worker")

    async def test_start_worker_unknown(
        self,
        supervisor: WorkerSupervisor,
    ) -> None:
        """Test starting unknown worker returns False."""
        result = await supervisor.start_worker("unknown")
        assert result is False

    async def test_start_worker_already_running(
        self,
        supervisor: WorkerSupervisor,
    ) -> None:
        """Test starting already running worker is idempotent."""

        async def worker() -> None:
            await asyncio.sleep(10)  # cancelled

        await supervisor.register_worker("test_worker", worker)
        await supervisor.start_worker("test_worker")

        try:
            # Start again - should return True (idempotent)
            result = await supervisor.start_worker("test_worker")
            assert result is True
        finally:
            await supervisor.stop_worker("test_worker")

    async def test_start_worker_resets_failed_state(
        self,
        supervisor: WorkerSupervisor,
    ) -> None:
        """Test starting a failed worker resets its state."""

        async def worker() -> None:
            await asyncio.sleep(10)  # cancelled

        await supervisor.register_worker("test_worker", worker)

        # Set to failed state
        supervisor._workers["test_worker"].status = WorkerStatus.FAILED
        supervisor._workers["test_worker"].restart_count = 5
        supervisor._workers["test_worker"].circuit_open = True

        await supervisor.start_worker("test_worker")

        try:
            info = supervisor.get_worker_info("test_worker")
            assert info is not None
            assert info.status == WorkerStatus.RUNNING
            assert info.restart_count == 0
            assert info.circuit_open is False
        finally:
            await supervisor.stop_worker("test_worker")

    async def test_stop_worker_manually(
        self,
        supervisor: WorkerSupervisor,
    ) -> None:
        """Test manually stopping a running worker."""

        async def worker() -> None:
            await asyncio.sleep(10)  # cancelled

        await supervisor.register_worker("test_worker", worker)
        await supervisor.start_worker("test_worker")
        await asyncio.sleep(0.1)  # Let it start

        result = await supervisor.stop_worker("test_worker")
        assert result is True
        assert supervisor.get_worker_status("test_worker") == WorkerStatus.STOPPED

    async def test_stop_worker_unknown(
        self,
        supervisor: WorkerSupervisor,
    ) -> None:
        """Test stopping unknown worker returns False."""
        result = await supervisor.stop_worker("unknown")
        assert result is False

    async def test_restart_worker_task_manually(
        self,
        supervisor: WorkerSupervisor,
    ) -> None:
        """Test manually restarting a worker."""
        call_count = 0

        async def worker() -> None:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(10)  # cancelled

        await supervisor.register_worker("test_worker", worker)
        await supervisor.start_worker("test_worker")
        await asyncio.sleep(0.1)  # Let it start

        # Restart
        result = await supervisor.restart_worker_task("test_worker")
        assert result is True
        await asyncio.sleep(0.1)  # Let it restart

        try:
            # Should have been called twice (initial + restart)
            assert call_count == 2
            assert supervisor.get_worker_status("test_worker") == WorkerStatus.RUNNING

            # Restart count should be reset for manual restart
            info = supervisor.get_worker_info("test_worker")
            assert info is not None
            assert info.restart_count == 0
        finally:
            await supervisor.stop_worker("test_worker")

    async def test_restart_worker_task_unknown(
        self,
        supervisor: WorkerSupervisor,
    ) -> None:
        """Test restarting unknown worker returns False."""
        result = await supervisor.restart_worker_task("unknown")
        assert result is False

    async def test_restart_worker_task_records_history(
        self,
        supervisor: WorkerSupervisor,
    ) -> None:
        """Test manual restart is recorded in history."""

        async def worker() -> None:
            await asyncio.sleep(10)  # cancelled

        await supervisor.register_worker("test_worker", worker)
        await supervisor.start_worker("test_worker")
        await asyncio.sleep(0.1)

        await supervisor.restart_worker_task("test_worker")

        try:
            history = supervisor.get_restart_history(worker_name="test_worker")
            assert len(history) >= 1
            assert history[0]["status"] == "success"
            assert history[0]["error"] == "Manual restart requested"
        finally:
            await supervisor.stop_worker("test_worker")


# ============================================================================
# Worker Pool Counts Tests
# ============================================================================


class TestWorkerPoolCounts:
    """Tests for get_worker_pool_counts method."""

    async def test_get_worker_pool_counts_all_stopped(
        self,
        supervisor: WorkerSupervisor,
    ) -> None:
        """Test pool counts with all workers stopped."""

        async def worker() -> None:
            pass

        await supervisor.register_worker("worker1", worker)
        await supervisor.register_worker("worker2", worker)

        active, busy, idle = supervisor.get_worker_pool_counts()
        assert active == 0
        assert busy == 0
        assert idle == 0

    async def test_get_worker_pool_counts_all_running(
        self,
        supervisor: WorkerSupervisor,
    ) -> None:
        """Test pool counts with all workers running."""

        async def worker() -> None:
            await asyncio.sleep(10)  # cancelled

        await supervisor.register_worker("worker1", worker)
        await supervisor.register_worker("worker2", worker)
        await supervisor.start()

        try:
            await asyncio.sleep(0.1)  # Let workers start

            active, busy, idle = supervisor.get_worker_pool_counts()
            assert active == 2
            assert busy == 2  # Running workers are considered busy
            assert idle == 0
        finally:
            await supervisor.stop()

    async def test_get_worker_pool_counts_mixed_states(
        self,
        supervisor: WorkerSupervisor,
    ) -> None:
        """Test pool counts with workers in mixed states."""

        async def worker() -> None:
            await asyncio.sleep(10)  # cancelled

        async def crashing_worker() -> None:
            raise RuntimeError("Crash")

        await supervisor.register_worker("worker1", worker)
        await supervisor.register_worker("worker2", crashing_worker, max_restarts=0)
        await supervisor.start()

        try:
            await asyncio.sleep(0.2)  # Let worker2 crash

            active, busy, idle = supervisor.get_worker_pool_counts()
            # Only worker1 should be running
            assert active == 1
            assert busy == 1
        finally:
            await supervisor.stop()


# ============================================================================
# Callback Tests (NEM-2460)
# ============================================================================


class TestCallbacks:
    """Tests for on_restart and on_failure callbacks (NEM-2460)."""

    async def test_on_restart_callback_called(
        self,
        supervisor_config: SupervisorConfig,
        mock_broadcaster: AsyncMock,
    ) -> None:
        """Test on_restart callback is called when worker restarts."""
        restart_calls = []

        async def on_restart(name: str, attempt: int, error: str | None) -> None:
            restart_calls.append({"name": name, "attempt": attempt, "error": error})

        supervisor = WorkerSupervisor(
            config=supervisor_config,
            broadcaster=mock_broadcaster,
            on_restart=on_restart,
        )

        call_count = 0

        async def flaky_worker() -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("First crash")
            await asyncio.sleep(10)  # cancelled

        await supervisor.register_worker("flaky_worker", flaky_worker, backoff_base=0.05)
        await supervisor.start()

        try:
            await asyncio.sleep(0.5)

            assert len(restart_calls) >= 1
            assert restart_calls[0]["name"] == "flaky_worker"
            assert restart_calls[0]["attempt"] >= 1
            assert "First crash" in restart_calls[0]["error"]
        finally:
            await supervisor.stop()

    async def test_on_failure_callback_called(
        self,
        supervisor_config: SupervisorConfig,
        mock_broadcaster: AsyncMock,
    ) -> None:
        """Test on_failure callback is called when worker exceeds max restarts."""
        failure_calls = []

        async def on_failure(name: str, error: str | None) -> None:
            failure_calls.append({"name": name, "error": error})

        supervisor = WorkerSupervisor(
            config=supervisor_config,
            broadcaster=mock_broadcaster,
            on_failure=on_failure,
        )

        async def always_crashes() -> None:
            raise RuntimeError("Always fails")

        await supervisor.register_worker(
            "always_crashes",
            always_crashes,
            max_restarts=1,
            backoff_base=0.05,
        )
        await supervisor.start()

        try:
            await asyncio.sleep(0.5)

            assert len(failure_calls) >= 1
            assert failure_calls[0]["name"] == "always_crashes"
            assert "Always fails" in failure_calls[0]["error"]
        finally:
            await supervisor.stop()

    async def test_on_restart_callback_exception_handled(
        self,
        supervisor_config: SupervisorConfig,
        mock_broadcaster: AsyncMock,
    ) -> None:
        """Test exception in on_restart callback is handled gracefully."""

        async def failing_on_restart(name: str, attempt: int, error: str | None) -> None:
            raise ValueError("Callback error")

        supervisor = WorkerSupervisor(
            config=supervisor_config,
            broadcaster=mock_broadcaster,
            on_restart=failing_on_restart,
        )

        call_count = 0

        async def flaky_worker() -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("First crash")
            await asyncio.sleep(10)  # cancelled

        await supervisor.register_worker("flaky_worker", flaky_worker, backoff_base=0.05)
        await supervisor.start()

        try:
            await asyncio.sleep(0.5)

            # Worker should still restart despite callback error
            assert call_count >= 2
        finally:
            await supervisor.stop()

    async def test_on_failure_callback_exception_handled(
        self,
        supervisor_config: SupervisorConfig,
        mock_broadcaster: AsyncMock,
    ) -> None:
        """Test exception in on_failure callback is handled gracefully."""

        async def failing_on_failure(name: str, error: str | None) -> None:
            raise ValueError("Callback error")

        supervisor = WorkerSupervisor(
            config=supervisor_config,
            broadcaster=mock_broadcaster,
            on_failure=failing_on_failure,
        )

        async def always_crashes() -> None:
            raise RuntimeError("Always fails")

        await supervisor.register_worker(
            "always_crashes",
            always_crashes,
            max_restarts=1,
            backoff_base=0.05,
        )
        await supervisor.start()

        try:
            await asyncio.sleep(0.5)

            # Worker should transition to FAILED despite callback error
            info = supervisor.get_worker_info("always_crashes")
            assert info is not None
            assert info.status == WorkerStatus.FAILED
        finally:
            await supervisor.stop()


# ============================================================================
# Unregister Worker with Running Task Tests
# ============================================================================


class TestUnregisterRunningWorker:
    """Tests for unregistering workers with running tasks."""

    async def test_unregister_worker_cancels_running_task(
        self,
        supervisor: WorkerSupervisor,
    ) -> None:
        """Test unregistering a worker cancels its running task."""
        task_cancelled = asyncio.Event()

        async def worker() -> None:
            try:
                await asyncio.sleep(10)  # cancelled
            except asyncio.CancelledError:
                task_cancelled.set()
                raise

        await supervisor.register_worker("test_worker", worker)
        await supervisor.start_worker("test_worker")
        await asyncio.sleep(0.1)  # Let it start

        await supervisor.unregister_worker("test_worker")

        # Task should have been cancelled
        await asyncio.wait_for(task_cancelled.wait(), timeout=1.0)
        assert "test_worker" not in supervisor._workers


# ============================================================================
# Heartbeat Monitoring Tests (NEM-4148)
# ============================================================================


class TestHeartbeatMonitoring:
    """Tests for heartbeat monitoring functionality (NEM-4148)."""

    async def test_record_heartbeat_success(self, supervisor: WorkerSupervisor) -> None:
        """Test recording a heartbeat for a registered worker."""

        async def worker() -> None:
            await asyncio.sleep(10)  # cancelled

        await supervisor.register_worker("test_worker", worker)

        result = supervisor.record_heartbeat("test_worker")
        assert result is True

        info = supervisor.get_worker_info("test_worker")
        assert info is not None
        assert info.last_heartbeat_at is not None

    async def test_record_heartbeat_unknown_worker(self, supervisor: WorkerSupervisor) -> None:
        """Test recording heartbeat for unknown worker returns False."""
        result = supervisor.record_heartbeat("unknown")
        assert result is False

    async def test_record_heartbeat_resets_missed_count(self, supervisor: WorkerSupervisor) -> None:
        """Test that recording heartbeat resets missed count."""

        async def worker() -> None:
            pass

        await supervisor.register_worker("test_worker", worker)

        # Manually set missed heartbeat count
        supervisor._workers["test_worker"].missed_heartbeat_count = 5

        supervisor.record_heartbeat("test_worker")

        info = supervisor.get_worker_info("test_worker")
        assert info is not None
        assert info.missed_heartbeat_count == 0

    async def test_get_missed_heartbeat_count(self, supervisor: WorkerSupervisor) -> None:
        """Test getting missed heartbeat count for a worker."""

        async def worker() -> None:
            pass

        await supervisor.register_worker("test_worker", worker)

        # Initially should be 0
        assert supervisor.get_missed_heartbeat_count("test_worker") == 0

        # Set a value
        supervisor._workers["test_worker"].missed_heartbeat_count = 3
        assert supervisor.get_missed_heartbeat_count("test_worker") == 3

    async def test_get_missed_heartbeat_count_unknown_worker(
        self, supervisor: WorkerSupervisor
    ) -> None:
        """Test getting missed heartbeat count for unknown worker returns 0."""
        assert supervisor.get_missed_heartbeat_count("unknown") == 0

    async def test_worker_info_to_dict_includes_heartbeat_fields(
        self, supervisor: WorkerSupervisor
    ) -> None:
        """Test that to_dict includes heartbeat fields."""

        async def worker() -> None:
            pass

        await supervisor.register_worker("test_worker", worker, heartbeat_timeout=60.0)
        supervisor.record_heartbeat("test_worker")

        info = supervisor.get_worker_info("test_worker")
        assert info is not None

        result = info.to_dict()
        assert "last_heartbeat_at" in result
        assert result["last_heartbeat_at"] is not None
        assert "heartbeat_timeout" in result
        assert result["heartbeat_timeout"] == 60.0
        assert "missed_heartbeat_count" in result
        assert result["missed_heartbeat_count"] == 0

    async def test_register_worker_with_custom_heartbeat_timeout(
        self, supervisor: WorkerSupervisor
    ) -> None:
        """Test registering a worker with custom heartbeat timeout."""

        async def worker() -> None:
            pass

        await supervisor.register_worker("test_worker", worker, heartbeat_timeout=120.0)

        info = supervisor.get_worker_info("test_worker")
        assert info is not None
        assert info.heartbeat_timeout == 120.0

    async def test_start_worker_initializes_heartbeat(self, supervisor: WorkerSupervisor) -> None:
        """Test that starting a worker initializes the heartbeat timestamp."""

        async def worker() -> None:
            await asyncio.sleep(10)  # cancelled

        await supervisor.register_worker("test_worker", worker)
        await supervisor.start_worker("test_worker")

        try:
            await asyncio.sleep(0.1)  # Let it start

            info = supervisor.get_worker_info("test_worker")
            assert info is not None
            assert info.last_heartbeat_at is not None
            assert info.missed_heartbeat_count == 0
        finally:
            await supervisor.stop_worker("test_worker")

    async def test_heartbeat_check_disabled(
        self,
        mock_broadcaster: AsyncMock,
    ) -> None:
        """Test that heartbeat check can be disabled."""
        from datetime import timedelta

        config = SupervisorConfig(
            check_interval=0.1,
            heartbeat_check_enabled=False,
            default_heartbeat_timeout=0.1,  # Very short
        )
        supervisor = WorkerSupervisor(config=config, broadcaster=mock_broadcaster)

        async def worker() -> None:
            await asyncio.sleep(10)  # cancelled

        await supervisor.register_worker("test_worker", worker)

        # Manually set old heartbeat
        from datetime import UTC, datetime

        supervisor._workers["test_worker"].last_heartbeat_at = datetime.now(UTC) - timedelta(
            hours=1
        )

        # Check heartbeat - should not increment missed count when disabled
        supervisor._check_worker_heartbeat("test_worker")

        info = supervisor.get_worker_info("test_worker")
        assert info is not None
        assert info.missed_heartbeat_count == 0  # Should remain 0 because disabled
