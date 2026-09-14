"""Tests for shutdown resource cleanup (NEM-1996, NEM-2006).

These tests verify that:
- AI models are properly unloaded from GPU memory during shutdown (NEM-1996)
- Background task queues are drained gracefully on shutdown (NEM-2006)
"""

from unittest.mock import AsyncMock, MagicMock

import pytest


class TestModelUnloading:
    """Tests for AI model unloading during shutdown."""

    @pytest.mark.asyncio
    async def test_model_manager_has_unload_all_method(self):
        """Verify ModelManager has unload_all method."""
        from backend.services.model_zoo import get_model_manager

        model_manager = get_model_manager()
        assert hasattr(model_manager, "unload_all")
        assert callable(model_manager.unload_all)

    @pytest.mark.asyncio
    async def test_model_manager_unload_all_is_async(self):
        """Verify ModelManager.unload_all() is an async method."""
        import inspect

        from backend.services.model_zoo import get_model_manager

        model_manager = get_model_manager()
        assert inspect.iscoroutinefunction(model_manager.unload_all)

    @pytest.mark.asyncio
    async def test_model_manager_unload_all_clears_loaded_models(self):
        """Verify unload_all clears the loaded models dictionary."""
        from backend.services.model_zoo import get_model_manager

        model_manager = get_model_manager()

        # Call unload_all
        await model_manager.unload_all()

        # Check that loaded_models is empty
        # This tests the actual behavior of the unload_all method
        status = model_manager.get_status()
        assert status["loaded_models"] == []


class TestShutdownCodePresence:
    """Tests to verify NEM-1996 shutdown code is present in main.py."""

    def test_shutdown_has_model_unload_code(self):
        """Verify main.py contains model unload code."""
        import inspect

        import backend.main

        # Read the source code of main.py
        source = inspect.getsource(backend.main)

        # Verify the NEM-1996 fix is present
        assert "NEM-1996" in source
        assert "unload_all" in source
        assert "get_model_manager" in source

    def test_shutdown_has_cuda_cache_clear(self):
        """Verify main.py contains CUDA cache clearing code."""
        import inspect

        import backend.main

        source = inspect.getsource(backend.main)

        # Verify CUDA cleanup is present
        assert "torch.cuda.empty_cache" in source or "empty_cache" in source


class TestGracefulShutdown:
    """Tests for graceful shutdown handling."""

    @pytest.mark.asyncio
    async def test_model_unload_handles_empty_state(self):
        """Verify unload_all works when no models are loaded."""
        from backend.services.model_zoo import get_model_manager

        model_manager = get_model_manager()

        # Should not raise even if no models are loaded
        await model_manager.unload_all()

    @pytest.mark.asyncio
    async def test_model_unload_is_idempotent(self):
        """Verify calling unload_all multiple times is safe."""
        from backend.services.model_zoo import get_model_manager

        model_manager = get_model_manager()

        # Call multiple times - should not raise
        await model_manager.unload_all()
        await model_manager.unload_all()
        await model_manager.unload_all()


class TestQueueDraining:
    """Tests for graceful queue draining during shutdown (NEM-2006)."""

    @pytest.mark.asyncio
    async def test_pipeline_manager_has_stop_accepting_method(self):
        """Verify PipelineWorkerManager has stop_accepting method."""
        from backend.services.pipeline_workers import PipelineWorkerManager

        assert hasattr(PipelineWorkerManager, "stop_accepting")
        assert callable(PipelineWorkerManager.stop_accepting)

    @pytest.mark.asyncio
    async def test_pipeline_manager_has_get_pending_count_method(self):
        """Verify PipelineWorkerManager has get_pending_count method."""
        import inspect

        from backend.services.pipeline_workers import PipelineWorkerManager

        assert hasattr(PipelineWorkerManager, "get_pending_count")
        assert inspect.iscoroutinefunction(PipelineWorkerManager.get_pending_count)

    @pytest.mark.asyncio
    async def test_pipeline_manager_has_drain_queues_method(self):
        """Verify PipelineWorkerManager has drain_queues method."""
        import inspect

        from backend.services.pipeline_workers import PipelineWorkerManager

        assert hasattr(PipelineWorkerManager, "drain_queues")
        assert inspect.iscoroutinefunction(PipelineWorkerManager.drain_queues)

    @pytest.mark.asyncio
    async def test_stop_accepting_sets_flag(self):
        """Verify stop_accepting sets the accepting flag to False."""
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
    async def test_stop_accepting_is_idempotent(self):
        """Verify calling stop_accepting multiple times is safe."""
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
    async def test_get_pending_count_returns_queue_depths(self):
        """Verify get_pending_count returns sum of queue depths."""
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
    async def test_get_pending_count_handles_redis_error(self):
        """Verify get_pending_count returns 0 on Redis error."""
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

    @pytest.mark.asyncio
    async def test_drain_queues_returns_zero_when_empty(self):
        """Verify drain_queues returns 0 when queues are empty."""
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
    async def test_drain_queues_times_out_with_stuck_queue(self):
        """Verify drain_queues returns remaining count on timeout."""
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
    async def test_status_includes_accepting_flag(self):
        """Verify get_status includes accepting flag."""
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


class TestQueueDrainingCodePresence:
    """Tests to verify NEM-2006 queue draining code is present in main.py."""

    def test_shutdown_has_queue_drain_code(self):
        """Verify main.py contains queue draining code."""
        import inspect

        import backend.main

        source = inspect.getsource(backend.main)

        # Verify the NEM-2006 fix is present
        assert "NEM-2006" in source
        assert "drain_queues" in source

    def test_drain_queues_import_exists(self):
        """Verify drain_queues is imported in main.py."""
        import inspect

        import backend.main

        source = inspect.getsource(backend.main)

        # Check that drain_queues is imported from pipeline_workers
        # The import may be single-line or multi-line formatted
        assert "from backend.services.pipeline_workers import" in source
        assert "drain_queues" in source

    def test_drain_queues_function_exists(self):
        """Verify drain_queues module-level function exists."""
        import inspect

        from backend.services.pipeline_workers import drain_queues

        assert inspect.iscoroutinefunction(drain_queues)

    @pytest.mark.asyncio
    async def test_drain_queues_module_function_returns_zero_when_no_manager(self):
        """Verify module-level drain_queues returns 0 when no manager exists."""
        from backend.services import pipeline_workers as pw

        # Temporarily reset the manager state
        original_manager = pw._pipeline_manager
        pw._pipeline_manager = None

        try:
            remaining = await pw.drain_queues(timeout=1.0)
            assert remaining == 0
        finally:
            pw._pipeline_manager = original_manager
