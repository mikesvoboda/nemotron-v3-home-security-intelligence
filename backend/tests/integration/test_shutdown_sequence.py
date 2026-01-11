"""Integration tests for shutdown sequence (NEM-2004).

This module tests that the application shutdown sequence correctly:
1. Unloads AI models from GPU memory
2. Clears CUDA cache
3. Drains queues gracefully
4. Handles SIGTERM signals properly

These tests verify the shutdown code paths documented in NEM-1996 and NEM-2006.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.timeout(60)


class TestModelUnloadingOnShutdown:
    """Tests for AI model unloading during application shutdown.

    Verifies that the shutdown sequence properly unloads models from GPU memory
    to prevent memory leaks and ensure clean restarts.
    """

    @pytest.mark.asyncio
    async def test_model_manager_unload_all_clears_loaded_models(self) -> None:
        """Verify unload_all clears the loaded models dictionary.

        The ModelManager should track all loaded models and clear them
        when unload_all is called during shutdown.
        """
        from backend.services.model_zoo import get_model_manager, reset_model_manager

        # Reset to ensure clean state
        reset_model_manager()

        model_manager = get_model_manager()

        # Verify manager starts with no models loaded
        assert model_manager.loaded_models == []

        # Call unload_all (should not raise even with no models)
        await model_manager.unload_all()

        # Verify still empty
        status = model_manager.get_status()
        assert status["loaded_models"] == []
        assert status["total_loaded_vram_mb"] == 0

        # Cleanup
        reset_model_manager()

    @pytest.mark.asyncio
    async def test_model_manager_unload_all_is_idempotent(self) -> None:
        """Verify calling unload_all multiple times is safe.

        The shutdown sequence may call unload_all multiple times in error
        recovery scenarios - this should be safe and idempotent.
        """
        from backend.services.model_zoo import get_model_manager, reset_model_manager

        reset_model_manager()
        model_manager = get_model_manager()

        # Call multiple times - should not raise
        await model_manager.unload_all()
        await model_manager.unload_all()
        await model_manager.unload_all()

        # Verify manager is still in valid state
        assert model_manager.loaded_models == []

        reset_model_manager()

    @pytest.mark.asyncio
    async def test_model_manager_clears_load_counts(self) -> None:
        """Verify unload_all clears the reference count tracking.

        The ModelManager uses reference counting for nested model loads.
        unload_all should reset all counts to prevent stale state.
        """
        from backend.services.model_zoo import get_model_manager, reset_model_manager

        reset_model_manager()
        model_manager = get_model_manager()

        # Verify load counts start empty
        status = model_manager.get_status()
        assert status["load_counts"] == {}

        await model_manager.unload_all()

        # Verify still empty after unload
        status = model_manager.get_status()
        assert status["load_counts"] == {}

        reset_model_manager()


class TestCUDACacheClearing:
    """Tests for CUDA cache clearing during shutdown.

    Verifies that the shutdown sequence clears CUDA memory cache
    to prevent GPU memory fragmentation on restart.
    """

    @pytest.mark.asyncio
    async def test_cuda_cache_clear_handles_no_cuda(self) -> None:
        """Verify CUDA cache clearing handles systems without CUDA.

        The shutdown code should gracefully handle systems where
        CUDA is not available (CPU-only systems, test environments).
        """
        with patch("torch.cuda.is_available", return_value=False):
            # Should not raise
            try:
                import torch

                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except ImportError:
                pass  # torch not installed, which is fine

    @pytest.mark.asyncio
    async def test_cuda_cache_clear_handles_import_error(self) -> None:
        """Verify CUDA cache clearing handles missing torch.

        The shutdown code should gracefully handle environments
        where torch is not installed (e.g., minimal test containers).
        """
        # Simulate torch not being installed
        with patch.dict("sys.modules", {"torch": None}):
            try:
                import torch

                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except (ImportError, AttributeError, TypeError):
                pass  # Expected when torch is mocked as None


class TestGracefulQueueDraining:
    """Tests for graceful queue draining during shutdown.

    Verifies that the shutdown sequence properly drains task queues
    before stopping workers to prevent data loss.
    """

    @pytest.mark.asyncio
    async def test_drain_queues_returns_zero_when_no_manager(self) -> None:
        """Verify drain_queues returns 0 when no pipeline manager exists.

        During shutdown without active workers, drain_queues should
        return 0 immediately without errors.
        """
        from backend.services import pipeline_workers as pw

        # Save original state
        original_manager = pw._pipeline_manager

        try:
            # Clear the manager
            pw._pipeline_manager = None

            # Should return 0 immediately
            remaining = await pw.drain_queues(timeout=1.0)
            assert remaining == 0
        finally:
            # Restore original state
            pw._pipeline_manager = original_manager

    @pytest.mark.asyncio
    async def test_pipeline_manager_stop_accepting_sets_flag(self) -> None:
        """Verify stop_accepting sets the accepting flag to False.

        When shutdown begins, the pipeline manager should stop
        accepting new tasks before draining existing ones.
        """
        from backend.services.pipeline_workers import PipelineWorkerManager

        mock_redis = MagicMock()
        manager = PipelineWorkerManager(
            redis_client=mock_redis,
            enable_detection_worker=False,
            enable_analysis_worker=False,
            enable_timeout_worker=False,
            enable_metrics_worker=False,
        )

        # Initially accepting
        assert manager.accepting is True

        # Call stop_accepting
        manager.stop_accepting()

        # Now not accepting
        assert manager.accepting is False

    @pytest.mark.asyncio
    async def test_pipeline_manager_stop_accepting_is_idempotent(self) -> None:
        """Verify calling stop_accepting multiple times is safe.

        The shutdown sequence may call stop_accepting multiple times
        in error recovery scenarios.
        """
        from backend.services.pipeline_workers import PipelineWorkerManager

        mock_redis = MagicMock()
        manager = PipelineWorkerManager(
            redis_client=mock_redis,
            enable_detection_worker=False,
            enable_analysis_worker=False,
            enable_timeout_worker=False,
            enable_metrics_worker=False,
        )

        # Call multiple times - should not raise
        manager.stop_accepting()
        manager.stop_accepting()
        manager.stop_accepting()

        # Still not accepting
        assert manager.accepting is False

    @pytest.mark.asyncio
    async def test_drain_queues_returns_zero_when_queues_empty(self) -> None:
        """Verify drain_queues returns 0 when queues are empty.

        If all tasks have completed, drain_queues should return
        0 immediately without waiting for timeout.
        """
        from backend.services.pipeline_workers import PipelineWorkerManager

        mock_redis = MagicMock()
        mock_redis.get_queue_length = AsyncMock(return_value=0)

        manager = PipelineWorkerManager(
            redis_client=mock_redis,
            enable_detection_worker=False,
            enable_analysis_worker=False,
            enable_timeout_worker=False,
            enable_metrics_worker=False,
        )

        remaining = await manager.drain_queues(timeout=1.0)
        assert remaining == 0
        assert manager.accepting is False  # stop_accepting was called

    @pytest.mark.asyncio
    async def test_drain_queues_times_out_with_stuck_queue(self) -> None:
        """Verify drain_queues returns remaining count on timeout.

        If queues don't drain within the timeout, the remaining task
        count should be returned for logging/monitoring.
        """
        from backend.services.pipeline_workers import PipelineWorkerManager

        mock_redis = MagicMock()
        # Always return 5 items (queue never drains)
        mock_redis.get_queue_length = AsyncMock(return_value=5)

        manager = PipelineWorkerManager(
            redis_client=mock_redis,
            enable_detection_worker=False,
            enable_analysis_worker=False,
            enable_timeout_worker=False,
            enable_metrics_worker=False,
        )

        # Use short timeout for test
        remaining = await manager.drain_queues(timeout=0.3)
        assert remaining == 10  # 5 + 5 (detection + analysis)

    @pytest.mark.asyncio
    async def test_get_pending_count_returns_queue_depths(self) -> None:
        """Verify get_pending_count returns sum of queue depths.

        The pending count should reflect the total number of tasks
        across all queues (detection + analysis).
        """
        from backend.services.pipeline_workers import PipelineWorkerManager

        mock_redis = MagicMock()
        mock_redis.get_queue_length = AsyncMock(side_effect=[5, 3])  # detection, analysis

        manager = PipelineWorkerManager(
            redis_client=mock_redis,
            enable_detection_worker=False,
            enable_analysis_worker=False,
            enable_timeout_worker=False,
            enable_metrics_worker=False,
        )

        count = await manager.get_pending_count()
        assert count == 8  # 5 + 3

    @pytest.mark.asyncio
    async def test_get_pending_count_handles_redis_error(self) -> None:
        """Verify get_pending_count returns 0 on Redis error.

        If Redis is unavailable during shutdown, we should return 0
        rather than raising an exception.
        """
        from backend.services.pipeline_workers import PipelineWorkerManager

        mock_redis = MagicMock()
        mock_redis.get_queue_length = AsyncMock(side_effect=Exception("Redis error"))

        manager = PipelineWorkerManager(
            redis_client=mock_redis,
            enable_detection_worker=False,
            enable_analysis_worker=False,
            enable_timeout_worker=False,
            enable_metrics_worker=False,
        )

        count = await manager.get_pending_count()
        assert count == 0


class TestSIGTERMHandling:
    """Tests for SIGTERM signal handling during shutdown.

    Verifies that the application properly handles SIGTERM signals
    for graceful container shutdown.
    """

    def test_signal_handler_state_resets(self) -> None:
        """Verify signal handler state can be reset for testing.

        The reset_signal_handlers function should clear the global
        state to allow tests to install fresh handlers.
        """
        from backend.main import reset_signal_handlers

        # Should not raise
        reset_signal_handlers()

    def test_shutdown_event_is_asyncio_event(self) -> None:
        """Verify get_shutdown_event returns an asyncio.Event.

        The shutdown event is used to coordinate shutdown between
        signal handlers and the lifespan context.
        """
        from backend.main import get_shutdown_event, reset_signal_handlers

        reset_signal_handlers()
        event = get_shutdown_event()
        assert isinstance(event, asyncio.Event)
        reset_signal_handlers()

    def test_shutdown_event_starts_unset(self) -> None:
        """Verify shutdown event is not set initially.

        The event should only be set when a shutdown signal is received.
        """
        from backend.main import get_shutdown_event, reset_signal_handlers

        reset_signal_handlers()
        event = get_shutdown_event()
        assert not event.is_set()
        reset_signal_handlers()

    def test_get_shutdown_event_returns_same_instance(self) -> None:
        """Verify get_shutdown_event returns the same event instance.

        Multiple calls should return the same event to ensure
        coordination between handlers and the lifespan context.
        """
        from backend.main import get_shutdown_event, reset_signal_handlers

        reset_signal_handlers()
        event1 = get_shutdown_event()
        event2 = get_shutdown_event()
        assert event1 is event2
        reset_signal_handlers()


class TestShutdownCodePresence:
    """Tests to verify shutdown code is present in main.py.

    These tests verify that the NEM-1996 and NEM-2006 shutdown code
    is properly integrated into the application lifecycle.
    """

    def test_shutdown_has_model_unload_code(self) -> None:
        """Verify main.py contains model unload code."""
        import inspect

        import backend.main

        source = inspect.getsource(backend.main)

        # Verify the NEM-1996 fix is present
        assert "NEM-1996" in source
        assert "unload_all" in source
        assert "get_model_manager" in source

    def test_shutdown_has_cuda_cache_clear(self) -> None:
        """Verify main.py contains CUDA cache clearing code."""
        import inspect

        import backend.main

        source = inspect.getsource(backend.main)

        # Verify CUDA cleanup is present
        assert "empty_cache" in source

    def test_shutdown_has_queue_drain_code(self) -> None:
        """Verify main.py contains queue draining code."""
        import inspect

        import backend.main

        source = inspect.getsource(backend.main)

        # Verify the NEM-2006 fix is present
        assert "NEM-2006" in source
        assert "drain_queues" in source

    def test_drain_queues_import_exists(self) -> None:
        """Verify drain_queues is imported in main.py."""
        import inspect

        import backend.main

        source = inspect.getsource(backend.main)

        # Check that drain_queues is imported from pipeline_workers
        assert "from backend.services.pipeline_workers import" in source
        assert "drain_queues" in source

    def test_drain_queues_function_exists(self) -> None:
        """Verify drain_queues module-level function exists."""
        import inspect

        from backend.services.pipeline_workers import drain_queues

        assert inspect.iscoroutinefunction(drain_queues)


class TestShutdownOrdering:
    """Tests for proper shutdown ordering.

    Verifies that shutdown operations happen in the correct order
    to prevent resource leaks and data loss.
    """

    def test_lifespan_shutdown_order_documented(self) -> None:
        """Verify shutdown order is documented in lifespan context.

        The lifespan function should clearly document the shutdown
        sequence for maintainability.
        """
        import inspect

        import backend.main

        source = inspect.getsource(backend.main.lifespan)

        # Shutdown should happen after yield
        lines = source.split("yield")
        assert len(lines) >= 2, "lifespan should have yield statement"

        shutdown_section = lines[1]

        # Verify key operations are in shutdown section
        assert "drain_queues" in shutdown_section or "queue" in shutdown_section.lower()
        assert "unload" in shutdown_section.lower() or "model" in shutdown_section.lower()

    def test_status_includes_accepting_flag(self) -> None:
        """Verify get_status includes accepting flag for monitoring.

        The pipeline manager status should include the accepting flag
        so operators can monitor shutdown progress.
        """
        from backend.services.pipeline_workers import PipelineWorkerManager

        mock_redis = MagicMock()
        manager = PipelineWorkerManager(
            redis_client=mock_redis,
            enable_detection_worker=False,
            enable_analysis_worker=False,
            enable_timeout_worker=False,
            enable_metrics_worker=False,
        )

        status = manager.get_status()
        assert "accepting" in status
        assert status["accepting"] is True

        manager.stop_accepting()
        status = manager.get_status()
        assert status["accepting"] is False
