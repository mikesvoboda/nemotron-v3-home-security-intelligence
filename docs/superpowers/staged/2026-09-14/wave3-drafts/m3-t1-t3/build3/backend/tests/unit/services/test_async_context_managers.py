"""Unit tests for async context manager support across services (NEM-1599).

This module tests that services with start()/stop() methods can be used
as async context managers, providing automatic cleanup on exit.

Services tested:
    - FileWatcher: File system monitoring service
    - GPUMonitor: GPU statistics polling service
    - CleanupService: Data retention cleanup service
    - EventBroadcaster: WebSocket event broadcasting service
    - SystemBroadcaster: System status broadcasting service

Acceptance Criteria:
    - All services implement __aenter__ and __aexit__ methods
    - __aenter__ calls start() and returns self
    - __aexit__ calls stop() even if an exception occurred
    - Services can be used with `async with` statements
    - Exception handling in __aexit__ is correct (no suppression)

Related Issues:
    - NEM-1599: Consolidate async context manager patterns across services
"""

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Mark all tests in this module as unit tests
pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def mock_settings_for_context_manager_tests():
    """Set up minimal environment for tests.

    This fixture sets DATABASE_URL so get_settings() doesn't fail when
    services are instantiated.
    """
    from backend.core.config import get_settings

    original_db_url = os.environ.get("DATABASE_URL")

    # Only set DATABASE_URL if not already set
    if not original_db_url:
        os.environ["DATABASE_URL"] = (
            "postgresql+asyncpg://test:test@localhost:5432/test"  # pragma: allowlist secret
        )
        get_settings.cache_clear()

    yield

    # Restore original state
    if original_db_url is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = original_db_url
    get_settings.cache_clear()


# =============================================================================
# FileWatcher Context Manager Tests
# =============================================================================


class TestFileWatcherContextManager:
    """Tests for FileWatcher async context manager support.

    FileWatcher monitors camera directories for new file uploads and queues
    them for AI processing. The context manager ensures the observer is
    stopped on exit.
    """

    @pytest.mark.asyncio
    async def test_aenter_calls_start_and_returns_self(self, tmp_path):
        """Verify __aenter__ calls start() and returns self.

        Given: A FileWatcher instance
        When: __aenter__ is called
        Then: start() is called and the instance is returned
        """
        from backend.services.file_watcher import FileWatcher

        watcher = FileWatcher(camera_root=str(tmp_path))

        # Mock start to avoid actual observer initialization
        watcher.start = AsyncMock()

        result = await watcher.__aenter__()

        watcher.start.assert_called_once()
        assert result is watcher

    @pytest.mark.asyncio
    async def test_aexit_calls_stop(self, tmp_path):
        """Verify __aexit__ calls stop().

        Given: A FileWatcher instance
        When: __aexit__ is called
        Then: stop() is called to cleanup resources
        """
        from backend.services.file_watcher import FileWatcher

        watcher = FileWatcher(camera_root=str(tmp_path))
        watcher.stop = AsyncMock()

        await watcher.__aexit__(None, None, None)

        watcher.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_aexit_calls_stop_on_exception(self, tmp_path):
        """Verify __aexit__ calls stop() even when exception occurred.

        Given: A FileWatcher used in async with that raises an exception
        When: The context manager exits due to exception
        Then: stop() is still called
        """
        from backend.services.file_watcher import FileWatcher

        watcher = FileWatcher(camera_root=str(tmp_path))
        watcher.stop = AsyncMock()

        # Simulate exception context
        await watcher.__aexit__(ValueError, ValueError("test"), None)

        watcher.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager_usage(self, tmp_path):
        """Verify FileWatcher can be used with async with statement.

        Given: A FileWatcher instance
        When: Used in an async with block
        Then: start() is called on entry and stop() on exit
        """
        from backend.services.file_watcher import FileWatcher

        watcher = FileWatcher(camera_root=str(tmp_path))

        # Track calls
        start_called = False
        stop_called = False

        async def mock_start():
            nonlocal start_called
            start_called = True
            watcher.running = True

        async def mock_stop():
            nonlocal stop_called
            stop_called = True
            watcher.running = False

        watcher.start = mock_start
        watcher.stop = mock_stop

        async with watcher as w:
            assert w is watcher
            assert start_called
            assert watcher.running

        assert stop_called


# =============================================================================
# GPUMonitor Context Manager Tests
# =============================================================================


class TestGPUMonitorContextManager:
    """Tests for GPUMonitor async context manager support.

    GPUMonitor polls GPU statistics and stores them in the database.
    The context manager ensures polling is stopped and NVML is shutdown.
    """

    @pytest.mark.asyncio
    async def test_aenter_calls_start_and_returns_self(self):
        """Verify __aenter__ calls start() and returns self.

        Given: A GPUMonitor instance
        When: __aenter__ is called
        Then: start() is called and the instance is returned
        """
        from backend.services.gpu_monitor import GPUMonitor

        monitor = GPUMonitor()
        monitor.start = AsyncMock()

        result = await monitor.__aenter__()

        monitor.start.assert_called_once()
        assert result is monitor

    @pytest.mark.asyncio
    async def test_aexit_calls_stop(self):
        """Verify __aexit__ calls stop().

        Given: A GPUMonitor instance
        When: __aexit__ is called
        Then: stop() is called to cleanup resources
        """
        from backend.services.gpu_monitor import GPUMonitor

        monitor = GPUMonitor()
        monitor.stop = AsyncMock()

        await monitor.__aexit__(None, None, None)

        monitor.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_aexit_calls_stop_on_exception(self):
        """Verify __aexit__ calls stop() even when exception occurred.

        Given: A GPUMonitor used in async with that raises an exception
        When: The context manager exits due to exception
        Then: stop() is still called
        """
        from backend.services.gpu_monitor import GPUMonitor

        monitor = GPUMonitor()
        monitor.stop = AsyncMock()

        await monitor.__aexit__(RuntimeError, RuntimeError("test"), None)

        monitor.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager_usage(self):
        """Verify GPUMonitor can be used with async with statement.

        Given: A GPUMonitor instance
        When: Used in an async with block
        Then: start() is called on entry and stop() on exit
        """
        from backend.services.gpu_monitor import GPUMonitor

        monitor = GPUMonitor()

        start_called = False
        stop_called = False

        async def mock_start():
            nonlocal start_called
            start_called = True
            monitor.running = True

        async def mock_stop():
            nonlocal stop_called
            stop_called = True
            monitor.running = False

        monitor.start = mock_start
        monitor.stop = mock_stop

        async with monitor as m:
            assert m is monitor
            assert start_called
            assert monitor.running

        assert stop_called


# =============================================================================
# CleanupService Context Manager Tests
# =============================================================================


class TestCleanupServiceContextManager:
    """Tests for CleanupService async context manager support.

    CleanupService runs scheduled cleanup of old data. The context manager
    ensures the cleanup task is cancelled on exit.
    """

    @pytest.mark.asyncio
    async def test_aenter_calls_start_and_returns_self(self):
        """Verify __aenter__ calls start() and returns self.

        Given: A CleanupService instance
        When: __aenter__ is called
        Then: start() is called and the instance is returned
        """
        from backend.services.cleanup_service import CleanupService

        service = CleanupService()
        service.start = AsyncMock()

        result = await service.__aenter__()

        service.start.assert_called_once()
        assert result is service

    @pytest.mark.asyncio
    async def test_aexit_calls_stop(self):
        """Verify __aexit__ calls stop().

        Given: A CleanupService instance
        When: __aexit__ is called
        Then: stop() is called to cleanup resources
        """
        from backend.services.cleanup_service import CleanupService

        service = CleanupService()
        service.stop = AsyncMock()

        await service.__aexit__(None, None, None)

        service.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_aexit_calls_stop_on_exception(self):
        """Verify __aexit__ calls stop() even when exception occurred.

        Given: A CleanupService used in async with that raises an exception
        When: The context manager exits due to exception
        Then: stop() is still called
        """
        from backend.services.cleanup_service import CleanupService

        service = CleanupService()
        service.stop = AsyncMock()

        await service.__aexit__(KeyError, KeyError("test"), None)

        service.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager_usage(self):
        """Verify CleanupService can be used with async with statement.

        Given: A CleanupService instance
        When: Used in an async with block
        Then: start() is called on entry and stop() on exit
        """
        from backend.services.cleanup_service import CleanupService

        service = CleanupService()

        start_called = False
        stop_called = False

        async def mock_start():
            nonlocal start_called
            start_called = True
            service.running = True

        async def mock_stop():
            nonlocal stop_called
            stop_called = True
            service.running = False

        service.start = mock_start
        service.stop = mock_stop

        async with service as s:
            assert s is service
            assert start_called
            assert service.running

        assert stop_called


# =============================================================================
# EventBroadcaster Context Manager Tests
# =============================================================================


class TestEventBroadcasterContextManager:
    """Tests for EventBroadcaster async context manager support.

    EventBroadcaster manages WebSocket connections and broadcasts events.
    The context manager ensures listeners are stopped and connections closed.
    """

    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client."""
        redis = MagicMock()
        redis.subscribe = AsyncMock(return_value=MagicMock())
        redis.unsubscribe = AsyncMock()
        redis.publish = AsyncMock(return_value=1)
        return redis

    @pytest.mark.asyncio
    async def test_aenter_calls_start_and_returns_self(self, mock_redis):
        """Verify __aenter__ calls start() and returns self.

        Given: An EventBroadcaster instance
        When: __aenter__ is called
        Then: start() is called and the instance is returned
        """
        from backend.services.event_broadcaster import EventBroadcaster

        broadcaster = EventBroadcaster(redis_client=mock_redis)
        broadcaster.start = AsyncMock()

        result = await broadcaster.__aenter__()

        broadcaster.start.assert_called_once()
        assert result is broadcaster

    @pytest.mark.asyncio
    async def test_aexit_calls_stop(self, mock_redis):
        """Verify __aexit__ calls stop().

        Given: An EventBroadcaster instance
        When: __aexit__ is called
        Then: stop() is called to cleanup resources
        """
        from backend.services.event_broadcaster import EventBroadcaster

        broadcaster = EventBroadcaster(redis_client=mock_redis)
        broadcaster.stop = AsyncMock()

        await broadcaster.__aexit__(None, None, None)

        broadcaster.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_aexit_calls_stop_on_exception(self, mock_redis):
        """Verify __aexit__ calls stop() even when exception occurred.

        Given: An EventBroadcaster used in async with that raises an exception
        When: The context manager exits due to exception
        Then: stop() is still called
        """
        from backend.services.event_broadcaster import EventBroadcaster

        broadcaster = EventBroadcaster(redis_client=mock_redis)
        broadcaster.stop = AsyncMock()

        await broadcaster.__aexit__(ConnectionError, ConnectionError("test"), None)

        broadcaster.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager_usage(self, mock_redis):
        """Verify EventBroadcaster can be used with async with statement.

        Given: An EventBroadcaster instance
        When: Used in an async with block
        Then: start() is called on entry and stop() on exit
        """
        from backend.services.event_broadcaster import EventBroadcaster

        broadcaster = EventBroadcaster(redis_client=mock_redis)

        start_called = False
        stop_called = False

        async def mock_start():
            nonlocal start_called
            start_called = True
            broadcaster._is_listening = True

        async def mock_stop():
            nonlocal stop_called
            stop_called = True
            broadcaster._is_listening = False

        broadcaster.start = mock_start
        broadcaster.stop = mock_stop

        async with broadcaster as b:
            assert b is broadcaster
            assert start_called
            assert broadcaster._is_listening

        assert stop_called


# =============================================================================
# SystemBroadcaster Context Manager Tests
# =============================================================================


class TestSystemBroadcasterContextManager:
    """Tests for SystemBroadcaster async context manager support.

    SystemBroadcaster periodically broadcasts system status to WebSocket clients.
    The context manager ensures broadcasting is stopped and pub/sub cleaned up.
    """

    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client."""
        redis = MagicMock()
        redis.subscribe_dedicated = AsyncMock(return_value=MagicMock())
        redis.publish = AsyncMock(return_value=1)
        return redis

    @pytest.mark.asyncio
    async def test_aenter_calls_start_and_returns_self(self, mock_redis):
        """Verify __aenter__ calls start() and returns self.

        Given: A SystemBroadcaster instance
        When: __aenter__ is called
        Then: start() is called and the instance is returned
        """
        from backend.services.system_broadcaster import SystemBroadcaster

        broadcaster = SystemBroadcaster(redis_client=mock_redis)
        broadcaster.start = AsyncMock()

        result = await broadcaster.__aenter__()

        broadcaster.start.assert_called_once()
        assert result is broadcaster

    @pytest.mark.asyncio
    async def test_aexit_calls_stop(self, mock_redis):
        """Verify __aexit__ calls stop().

        Given: A SystemBroadcaster instance
        When: __aexit__ is called
        Then: stop() is called to cleanup resources
        """
        from backend.services.system_broadcaster import SystemBroadcaster

        broadcaster = SystemBroadcaster(redis_client=mock_redis)
        broadcaster.stop = AsyncMock()

        await broadcaster.__aexit__(None, None, None)

        broadcaster.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_aexit_calls_stop_on_exception(self, mock_redis):
        """Verify __aexit__ calls stop() even when exception occurred.

        Given: A SystemBroadcaster used in async with that raises an exception
        When: The context manager exits due to exception
        Then: stop() is still called
        """
        from backend.services.system_broadcaster import SystemBroadcaster

        broadcaster = SystemBroadcaster(redis_client=mock_redis)
        broadcaster.stop = AsyncMock()

        await broadcaster.__aexit__(TimeoutError, TimeoutError("test"), None)

        broadcaster.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager_usage(self, mock_redis):
        """Verify SystemBroadcaster can be used with async with statement.

        Given: A SystemBroadcaster instance
        When: Used in an async with block
        Then: start() is called on entry and stop() on exit
        """
        from backend.services.system_broadcaster import SystemBroadcaster

        broadcaster = SystemBroadcaster(redis_client=mock_redis)

        start_called = False
        stop_called = False

        async def mock_start(interval: float = 5.0):
            nonlocal start_called
            start_called = True
            broadcaster._running = True

        async def mock_stop():
            nonlocal stop_called
            stop_called = True
            broadcaster._running = False

        broadcaster.start = mock_start
        broadcaster.stop = mock_stop

        async with broadcaster as b:
            assert b is broadcaster
            assert start_called
            assert broadcaster._running

        assert stop_called

    @pytest.mark.asyncio
    async def test_start_stop_aliases(self, mock_redis):
        """Verify start() and stop() are aliases for start_broadcasting/stop_broadcasting.

        Given: A SystemBroadcaster instance
        When: start() and stop() are called
        Then: They delegate to start_broadcasting() and stop_broadcasting()
        """
        from backend.services.system_broadcaster import SystemBroadcaster

        broadcaster = SystemBroadcaster(redis_client=mock_redis)

        # Mock the underlying methods
        broadcaster.start_broadcasting = AsyncMock()
        broadcaster.stop_broadcasting = AsyncMock()

        await broadcaster.start(interval=10.0)
        broadcaster.start_broadcasting.assert_called_once_with(10.0)

        await broadcaster.stop()
        broadcaster.stop_broadcasting.assert_called_once()


# =============================================================================
# Integration Tests: Exception Propagation
# =============================================================================


class TestContextManagerExceptionPropagation:
    """Tests verifying that exceptions are not suppressed by context managers.

    The __aexit__ method should return None (not True), ensuring exceptions
    raised within the async with block are propagated to the caller.
    """

    @pytest.mark.asyncio
    async def test_file_watcher_propagates_exceptions(self, tmp_path):
        """Verify FileWatcher does not suppress exceptions."""
        from backend.services.file_watcher import FileWatcher

        watcher = FileWatcher(camera_root=str(tmp_path))
        watcher.start = AsyncMock()
        watcher.stop = AsyncMock()

        with pytest.raises(ValueError, match="test error"):
            async with watcher:
                raise ValueError("test error")

        # stop should still have been called
        watcher.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_gpu_monitor_propagates_exceptions(self):
        """Verify GPUMonitor does not suppress exceptions."""
        from backend.services.gpu_monitor import GPUMonitor

        monitor = GPUMonitor()
        monitor.start = AsyncMock()
        monitor.stop = AsyncMock()

        with pytest.raises(RuntimeError, match="test error"):
            async with monitor:
                raise RuntimeError("test error")

        monitor.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_service_propagates_exceptions(self):
        """Verify CleanupService does not suppress exceptions."""
        from backend.services.cleanup_service import CleanupService

        service = CleanupService()
        service.start = AsyncMock()
        service.stop = AsyncMock()

        with pytest.raises(KeyError, match="test error"):
            async with service:
                raise KeyError("test error")

        service.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_event_broadcaster_propagates_exceptions(self):
        """Verify EventBroadcaster does not suppress exceptions."""
        from backend.services.event_broadcaster import EventBroadcaster

        mock_redis = MagicMock()
        broadcaster = EventBroadcaster(redis_client=mock_redis)
        broadcaster.start = AsyncMock()
        broadcaster.stop = AsyncMock()

        with pytest.raises(ConnectionError, match="test error"):
            async with broadcaster:
                raise ConnectionError("test error")

        broadcaster.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_system_broadcaster_propagates_exceptions(self):
        """Verify SystemBroadcaster does not suppress exceptions."""
        from backend.services.system_broadcaster import SystemBroadcaster

        mock_redis = MagicMock()
        broadcaster = SystemBroadcaster(redis_client=mock_redis)
        broadcaster.start = AsyncMock()
        broadcaster.stop = AsyncMock()

        with pytest.raises(TimeoutError, match="test error"):
            async with broadcaster:
                raise TimeoutError("test error")

        broadcaster.stop.assert_called_once()


# =============================================================================
# Integration Tests: Real Start/Stop Behavior
# =============================================================================


class TestContextManagerRealBehavior:
    """Tests verifying the actual start/stop behavior (not mocked).

    These tests use the real start/stop implementations but mock
    external dependencies like Redis and database connections.
    """

    @pytest.mark.asyncio
    async def test_cleanup_service_real_lifecycle(self):
        """Verify CleanupService real start/stop through context manager.

        Given: A CleanupService instance
        When: Used in an async with block
        Then: The service is actually started and stopped
        """
        from backend.services.cleanup_service import CleanupService

        service = CleanupService()

        assert not service.running
        assert service._cleanup_task is None

        async with service:
            assert service.running
            assert service._cleanup_task is not None

        # Give cleanup task time to be cancelled
        await asyncio.sleep(0.01)

        assert not service.running
        assert service._cleanup_task is None

    @pytest.mark.asyncio
    async def test_gpu_monitor_real_lifecycle(self):
        """Verify GPUMonitor real start/stop through context manager.

        Given: A GPUMonitor instance
        When: Used in an async with block
        Then: The service is actually started and stopped
        """
        from backend.services.gpu_monitor import GPUMonitor

        # Mock database operations and pynvml (imported dynamically inside methods)
        with patch("backend.services.gpu_monitor.get_session"):
            monitor = GPUMonitor()

            assert not monitor.running
            assert monitor._poll_task is None

            # Patch the poll method to avoid actual GPU calls
            async def mock_poll_loop():
                while monitor.running:
                    await asyncio.sleep(0.1)

            monitor._poll_loop = mock_poll_loop

            async with monitor:
                assert monitor.running
                assert monitor._poll_task is not None

            # Give poll task time to be cancelled
            await asyncio.sleep(0.01)

            assert not monitor.running
            assert monitor._poll_task is None
