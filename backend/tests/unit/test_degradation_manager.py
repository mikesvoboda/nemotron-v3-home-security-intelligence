"""Unit tests for graceful degradation manager.

Tests cover:
- Mode transitions (normal, degraded, maintenance)
- Service state tracking
- Fallback behavior activation
- Recovery detection
- Integration with circuit breakers
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    reset_circuit_breakers,
)
from backend.services.degradation_manager import (
    DegradationManager,
    DegradationMode,
    FallbackQueue,
    ServiceDependency,
    ServiceState,
    ServiceStatus,
    get_degradation_manager,
    reset_degradation_manager,
)

# Fixtures


@pytest.fixture
def temp_fallback_dir(tmp_path) -> Path:
    """Create temporary directory for fallback queue."""
    fallback_dir = tmp_path / "fallback"
    fallback_dir.mkdir()
    return fallback_dir


@pytest.fixture
def mock_redis_client():
    """Mock Redis client."""
    mock = AsyncMock()
    mock.health_check = AsyncMock(return_value={"status": "healthy"})
    mock.add_to_queue = AsyncMock(return_value=1)
    mock.get_from_queue = AsyncMock(return_value=None)
    mock.get_queue_length = AsyncMock(return_value=0)
    return mock


@pytest.fixture
def degradation_manager(temp_fallback_dir, mock_redis_client) -> DegradationManager:
    """Create degradation manager for testing."""
    manager = DegradationManager(
        fallback_dir=str(temp_fallback_dir),
        redis_client=mock_redis_client,
        check_interval=0.1,
    )
    return manager


@pytest.fixture(autouse=True)
def reset_globals():
    """Reset global state before and after each test."""
    reset_circuit_breakers()
    reset_degradation_manager()
    yield
    reset_circuit_breakers()
    reset_degradation_manager()


# Mode enumeration tests


def test_degradation_mode_values():
    """Test DegradationMode enum values."""
    assert DegradationMode.NORMAL.value == "normal"
    assert DegradationMode.DEGRADED.value == "degraded"
    assert DegradationMode.MAINTENANCE.value == "maintenance"


# Service status tests


def test_service_status_values():
    """Test ServiceStatus enum values."""
    assert ServiceStatus.HEALTHY.value == "healthy"
    assert ServiceStatus.UNHEALTHY.value == "unhealthy"
    assert ServiceStatus.UNKNOWN.value == "unknown"


# Service state tests


def test_service_state_initialization():
    """Test ServiceState initialization."""
    state = ServiceState(
        name="redis",
        status=ServiceStatus.HEALTHY,
    )
    assert state.name == "redis"
    assert state.status == ServiceStatus.HEALTHY
    assert state.last_check is None
    assert state.consecutive_failures == 0


def test_service_state_to_dict():
    """Test ServiceState serialization."""
    state = ServiceState(
        name="rtdetr",
        status=ServiceStatus.UNHEALTHY,
        consecutive_failures=3,
        last_error="Connection refused",
    )
    data = state.to_dict()

    assert data["name"] == "rtdetr"
    assert data["status"] == "unhealthy"
    assert data["consecutive_failures"] == 3
    assert data["last_error"] == "Connection refused"


# Service dependency tests


def test_service_dependency_initialization():
    """Test ServiceDependency initialization."""
    dep = ServiceDependency(
        name="nemotron",
        health_check_url="http://localhost:8002/health",
        required=True,
    )
    assert dep.name == "nemotron"
    assert dep.health_check_url == "http://localhost:8002/health"
    assert dep.required is True
    assert dep.timeout == 5.0


# Fallback queue tests


def test_fallback_queue_initialization(temp_fallback_dir):
    """Test FallbackQueue initialization."""
    queue = FallbackQueue(
        queue_name="detection_queue",
        fallback_dir=str(temp_fallback_dir),
    )
    assert queue.queue_name == "detection_queue"
    assert queue.fallback_dir == temp_fallback_dir / "detection_queue"
    assert queue.count() == 0


@pytest.mark.asyncio
async def test_fallback_queue_add_item(temp_fallback_dir):
    """Test adding items to fallback queue."""
    queue = FallbackQueue(
        queue_name="test_queue",
        fallback_dir=str(temp_fallback_dir),
    )

    item = {"camera_id": "cam1", "file_path": "/path/to/image.jpg"}
    await queue.add(item)

    assert queue.count() == 1


@pytest.mark.asyncio
async def test_fallback_queue_get_item(temp_fallback_dir):
    """Test retrieving items from fallback queue."""
    queue = FallbackQueue(
        queue_name="test_queue",
        fallback_dir=str(temp_fallback_dir),
    )

    item = {"camera_id": "cam1", "file_path": "/path/to/image.jpg"}
    await queue.add(item)

    retrieved = await queue.get()
    assert retrieved is not None
    assert retrieved["camera_id"] == "cam1"
    assert queue.count() == 0


@pytest.mark.asyncio
async def test_fallback_queue_fifo_order(temp_fallback_dir):
    """Test fallback queue maintains FIFO order."""
    queue = FallbackQueue(
        queue_name="test_queue",
        fallback_dir=str(temp_fallback_dir),
    )

    await queue.add({"order": 1})
    await queue.add({"order": 2})
    await queue.add({"order": 3})

    assert (await queue.get())["order"] == 1
    assert (await queue.get())["order"] == 2
    assert (await queue.get())["order"] == 3


@pytest.mark.asyncio
async def test_fallback_queue_persists_to_disk(temp_fallback_dir):
    """Test fallback queue persists items to disk."""
    queue = FallbackQueue(
        queue_name="persist_queue",
        fallback_dir=str(temp_fallback_dir),
    )

    await queue.add({"data": "test"})

    # Check file was created
    queue_dir = temp_fallback_dir / "persist_queue"
    assert queue_dir.exists()
    files = list(queue_dir.glob("*.json"))
    assert len(files) == 1


@pytest.mark.asyncio
async def test_fallback_queue_empty_returns_none(temp_fallback_dir):
    """Test empty fallback queue returns None."""
    queue = FallbackQueue(
        queue_name="empty_queue",
        fallback_dir=str(temp_fallback_dir),
    )

    result = await queue.get()
    assert result is None


# Degradation manager initialization tests


def test_degradation_manager_initialization(degradation_manager):
    """Test DegradationManager initialization."""
    assert degradation_manager.mode == DegradationMode.NORMAL
    assert isinstance(degradation_manager.service_states, dict)


def test_degradation_manager_registers_services(degradation_manager):
    """Test DegradationManager can register service dependencies."""
    dep = ServiceDependency(
        name="rtdetr",
        health_check_url="http://localhost:8001/health",
        required=True,
    )
    degradation_manager.register_dependency(dep)

    assert "rtdetr" in degradation_manager._dependencies


# Mode transition tests


@pytest.mark.asyncio
async def test_mode_transition_normal_to_degraded(degradation_manager):
    """Test transition from normal to degraded mode."""
    assert degradation_manager.mode == DegradationMode.NORMAL

    await degradation_manager.enter_degraded_mode("rtdetr unavailable")

    assert degradation_manager.mode == DegradationMode.DEGRADED


@pytest.mark.asyncio
async def test_mode_transition_degraded_to_normal(degradation_manager):
    """Test transition from degraded to normal mode."""
    await degradation_manager.enter_degraded_mode("test")
    assert degradation_manager.mode == DegradationMode.DEGRADED

    await degradation_manager.enter_normal_mode()

    assert degradation_manager.mode == DegradationMode.NORMAL


@pytest.mark.asyncio
async def test_mode_transition_to_maintenance(degradation_manager):
    """Test transition to maintenance mode."""
    await degradation_manager.enter_maintenance_mode("Scheduled maintenance")

    assert degradation_manager.mode == DegradationMode.MAINTENANCE


@pytest.mark.asyncio
async def test_maintenance_mode_exits_to_normal(degradation_manager):
    """Test exiting maintenance mode returns to normal."""
    await degradation_manager.enter_maintenance_mode("test")

    await degradation_manager.exit_maintenance_mode()

    assert degradation_manager.mode == DegradationMode.NORMAL


# Service state tracking tests


@pytest.mark.asyncio
async def test_update_service_state(degradation_manager):
    """Test updating service state."""
    await degradation_manager.update_service_state(
        "redis",
        ServiceStatus.HEALTHY,
    )

    state = degradation_manager.get_service_state("redis")
    assert state is not None
    assert state.status == ServiceStatus.HEALTHY


@pytest.mark.asyncio
async def test_service_state_tracks_failures(degradation_manager):
    """Test service state tracks consecutive failures."""
    for _ in range(3):
        await degradation_manager.update_service_state(
            "rtdetr",
            ServiceStatus.UNHEALTHY,
            error="Connection refused",
        )

    state = degradation_manager.get_service_state("rtdetr")
    assert state.consecutive_failures == 3
    assert state.last_error == "Connection refused"


@pytest.mark.asyncio
async def test_service_state_resets_on_healthy(degradation_manager):
    """Test service state resets failures on healthy status."""
    # Record some failures
    for _ in range(3):
        await degradation_manager.update_service_state(
            "rtdetr",
            ServiceStatus.UNHEALTHY,
        )

    # Record healthy
    await degradation_manager.update_service_state(
        "rtdetr",
        ServiceStatus.HEALTHY,
    )

    state = degradation_manager.get_service_state("rtdetr")
    assert state.consecutive_failures == 0
    assert state.last_error is None


# Fallback behavior tests


@pytest.mark.asyncio
async def test_queue_to_fallback_when_redis_down(degradation_manager, temp_fallback_dir):
    """Test items are queued to fallback when Redis is down."""
    # Mark Redis as unhealthy
    await degradation_manager.update_service_state("redis", ServiceStatus.UNHEALTHY)
    await degradation_manager.enter_degraded_mode("Redis down")

    item = {"camera_id": "cam1", "file_path": "/path/to/image.jpg"}
    success = await degradation_manager.queue_with_fallback(
        "detection_queue",
        item,
    )

    assert success is True

    # Check item is in fallback
    fallback = degradation_manager._get_fallback_queue("detection_queue")
    assert fallback.count() == 1


@pytest.mark.asyncio
async def test_queue_to_redis_when_healthy(degradation_manager, mock_redis_client):
    """Test items are queued to Redis when healthy."""
    await degradation_manager.update_service_state("redis", ServiceStatus.HEALTHY)

    item = {"camera_id": "cam1", "file_path": "/path/to/image.jpg"}
    success = await degradation_manager.queue_with_fallback(
        "detection_queue",
        item,
    )

    assert success is True
    mock_redis_client.add_to_queue.assert_called_once()


# Recovery detection tests


@pytest.mark.asyncio
async def test_recovery_detected_on_service_healthy(degradation_manager):
    """Test recovery is detected when service becomes healthy."""
    # Register required dependency
    dep = ServiceDependency(
        name="rtdetr",
        health_check_url="http://localhost:8001/health",
        required=True,
    )
    degradation_manager.register_dependency(dep)

    # Simulate failure then recovery
    await degradation_manager.update_service_state("rtdetr", ServiceStatus.UNHEALTHY)
    await degradation_manager.enter_degraded_mode("rtdetr down")

    await degradation_manager.update_service_state("rtdetr", ServiceStatus.HEALTHY)
    await degradation_manager.check_recovery()

    assert degradation_manager.mode == DegradationMode.NORMAL


@pytest.mark.asyncio
async def test_no_recovery_if_required_service_unhealthy(degradation_manager):
    """Test no recovery if required service still unhealthy."""
    dep = ServiceDependency(
        name="rtdetr",
        health_check_url="http://localhost:8001/health",
        required=True,
    )
    degradation_manager.register_dependency(dep)

    await degradation_manager.update_service_state("rtdetr", ServiceStatus.UNHEALTHY)
    await degradation_manager.enter_degraded_mode("rtdetr down")

    await degradation_manager.check_recovery()

    assert degradation_manager.mode == DegradationMode.DEGRADED


# Circuit breaker integration tests


@pytest.mark.asyncio
async def test_circuit_breaker_failure_triggers_degraded(degradation_manager):
    """Test circuit breaker failures trigger degraded mode."""
    # Register rtdetr as a required dependency first
    dep = ServiceDependency(
        name="rtdetr",
        health_check_url="http://localhost:8001/health",
        required=True,
    )
    degradation_manager.register_dependency(dep)

    cb = CircuitBreaker(
        name="rtdetr",
        config=CircuitBreakerConfig(failure_threshold=2),
    )

    # Register circuit breaker
    degradation_manager.register_circuit_breaker(cb)

    # Trigger failures to open circuit
    async def failing_op():
        raise ValueError("Service unavailable")

    for _ in range(2):
        with pytest.raises(ValueError):
            await cb.call(failing_op)

    # Signal that circuit opened (triggers degraded mode for required services)
    await degradation_manager.on_circuit_opened("rtdetr")

    assert degradation_manager.mode == DegradationMode.DEGRADED


@pytest.mark.asyncio
async def test_circuit_breaker_recovery_triggers_check(degradation_manager):
    """Test circuit breaker recovery triggers recovery check."""
    cb = CircuitBreaker(
        name="rtdetr",
        config=CircuitBreakerConfig(
            failure_threshold=2,
            success_threshold=1,
            timeout_seconds=0.1,
        ),
    )

    degradation_manager.register_circuit_breaker(cb)

    # Open circuit
    async def failing_op():
        raise ValueError("Service unavailable")

    for _ in range(2):
        with pytest.raises(ValueError):
            await cb.call(failing_op)

    await degradation_manager.on_circuit_opened("rtdetr")

    # Wait for timeout and recover
    await asyncio.sleep(0.15)

    async def success_op():
        return "success"

    await cb.call(success_op)

    # Trigger recovery check
    await degradation_manager.on_circuit_closed("rtdetr")

    # In this test mode should return to normal as no required deps are unhealthy
    assert degradation_manager.mode == DegradationMode.NORMAL


# Drain fallback queue tests


@pytest.mark.asyncio
async def test_drain_fallback_queue(degradation_manager, mock_redis_client, temp_fallback_dir):
    """Test draining fallback queue to Redis."""
    # Add items to fallback
    fallback = degradation_manager._get_fallback_queue("detection_queue")
    await fallback.add({"order": 1})
    await fallback.add({"order": 2})
    await fallback.add({"order": 3})

    assert fallback.count() == 3

    # Drain to Redis
    drained = await degradation_manager.drain_fallback_queue("detection_queue")

    assert drained == 3
    assert fallback.count() == 0
    assert mock_redis_client.add_to_queue.call_count == 3


@pytest.mark.asyncio
async def test_drain_fallback_stops_on_redis_failure(
    degradation_manager, mock_redis_client, temp_fallback_dir
):
    """Test draining stops if Redis fails during drain."""
    fallback = degradation_manager._get_fallback_queue("detection_queue")
    await fallback.add({"order": 1})
    await fallback.add({"order": 2})
    await fallback.add({"order": 3})

    # Make Redis fail after first item
    call_count = 0

    async def failing_add(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count > 1:
            raise ConnectionError("Redis connection lost")
        return 1

    mock_redis_client.add_to_queue.side_effect = failing_add

    drained = await degradation_manager.drain_fallback_queue("detection_queue")

    # Should have drained one item before failure
    assert drained == 1
    # Remaining items should still be in fallback
    assert fallback.count() == 2


# Status reporting tests


def test_get_status(degradation_manager):
    """Test getting overall status."""
    status = degradation_manager.get_status()

    assert "mode" in status
    assert "services" in status
    assert status["mode"] == "normal"


@pytest.mark.asyncio
async def test_status_includes_service_states(degradation_manager):
    """Test status includes service states."""
    await degradation_manager.update_service_state("redis", ServiceStatus.HEALTHY)
    await degradation_manager.update_service_state("rtdetr", ServiceStatus.UNHEALTHY)

    status = degradation_manager.get_status()

    assert "redis" in status["services"]
    assert "rtdetr" in status["services"]
    assert status["services"]["redis"]["status"] == "healthy"
    assert status["services"]["rtdetr"]["status"] == "unhealthy"


# Global manager tests


def test_get_degradation_manager():
    """Test getting global degradation manager."""
    manager = get_degradation_manager()
    assert manager is not None
    assert isinstance(manager, DegradationManager)


def test_get_degradation_manager_returns_same_instance():
    """Test get_degradation_manager returns same instance."""
    manager1 = get_degradation_manager()
    manager2 = get_degradation_manager()
    assert manager1 is manager2


def test_reset_degradation_manager():
    """Test reset_degradation_manager clears global instance."""
    manager1 = get_degradation_manager()
    reset_degradation_manager()
    manager2 = get_degradation_manager()

    assert manager1 is not manager2


# Edge case tests


@pytest.mark.asyncio
async def test_multiple_services_unhealthy(degradation_manager):
    """Test handling multiple unhealthy services."""
    dep1 = ServiceDependency(name="rtdetr", health_check_url="http://localhost:8001/health")
    dep2 = ServiceDependency(name="nemotron", health_check_url="http://localhost:8002/health")

    degradation_manager.register_dependency(dep1)
    degradation_manager.register_dependency(dep2)

    await degradation_manager.update_service_state("rtdetr", ServiceStatus.UNHEALTHY)
    await degradation_manager.update_service_state("nemotron", ServiceStatus.UNHEALTHY)

    status = degradation_manager.get_status()
    unhealthy_count = sum(1 for s in status["services"].values() if s["status"] == "unhealthy")
    assert unhealthy_count == 2


@pytest.mark.asyncio
async def test_fallback_queue_limit(temp_fallback_dir):
    """Test fallback queue respects size limit."""
    queue = FallbackQueue(
        queue_name="limited_queue",
        fallback_dir=str(temp_fallback_dir),
        max_size=3,
    )

    for i in range(5):
        await queue.add({"order": i})

    # Should only have max_size items (oldest dropped)
    assert queue.count() == 3


@pytest.mark.asyncio
async def test_graceful_redis_reconnection(degradation_manager, mock_redis_client):
    """Test graceful handling of Redis reconnection."""
    # Start healthy
    await degradation_manager.update_service_state("redis", ServiceStatus.HEALTHY)

    # Redis fails
    mock_redis_client.add_to_queue.side_effect = ConnectionError("Connection lost")
    await degradation_manager.update_service_state("redis", ServiceStatus.UNHEALTHY)

    # Queue should go to fallback
    success = await degradation_manager.queue_with_fallback(
        "detection_queue",
        {"data": "test"},
    )
    assert success is True

    # Redis recovers
    mock_redis_client.add_to_queue.side_effect = None
    mock_redis_client.add_to_queue.return_value = 1
    await degradation_manager.update_service_state("redis", ServiceStatus.HEALTHY)

    # Queue should go to Redis
    success = await degradation_manager.queue_with_fallback(
        "detection_queue",
        {"data": "test2"},
    )
    assert success is True
    mock_redis_client.add_to_queue.assert_called()


# Health check integration tests


@pytest.mark.asyncio
async def test_health_check_loop_updates_states(degradation_manager):
    """Test health check loop updates service states."""
    dep = ServiceDependency(
        name="test_service",
        health_check_url="http://localhost:9999/health",
        timeout=0.1,
    )
    degradation_manager.register_dependency(dep)

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = ConnectionError("Connection refused")

        await degradation_manager._check_dependency(dep)

    state = degradation_manager.get_service_state("test_service")
    assert state.status == ServiceStatus.UNHEALTHY


@pytest.mark.asyncio
async def test_health_check_success_updates_state(degradation_manager):
    """Test successful health check updates state to healthy."""
    dep = ServiceDependency(
        name="healthy_service",
        health_check_url="http://localhost:8001/health",
    )
    degradation_manager.register_dependency(dep)

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_get.return_value.__aexit__ = AsyncMock(return_value=None)

        await degradation_manager._check_dependency(dep)

    state = degradation_manager.get_service_state("healthy_service")
    assert state.status == ServiceStatus.HEALTHY
