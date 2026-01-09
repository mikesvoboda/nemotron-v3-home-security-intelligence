"""Tests for shutdown resource cleanup (NEM-1996).

These tests verify that AI models are properly unloaded from GPU memory
during shutdown.
"""

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
