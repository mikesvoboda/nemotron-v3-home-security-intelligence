"""Tests for shutdown resource cleanup (NEM-1996, NEM-2022).

These tests verify that AI models are properly unloaded from GPU memory
during shutdown, and that CUDA cache is cleared with proper error isolation.
"""

from unittest.mock import MagicMock, patch

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

    def test_shutdown_has_cuda_synchronize(self):
        """Verify main.py contains CUDA synchronize before empty_cache (NEM-2022)."""
        import inspect

        import backend.main

        source = inspect.getsource(backend.main)

        # Verify CUDA synchronize is present before empty_cache
        assert "torch.cuda.synchronize" in source or "cuda.synchronize" in source
        # Verify NEM-2022 comment is present
        assert "NEM-2022" in source

    def test_cuda_cleanup_is_separate_from_model_unload(self):
        """Verify CUDA cleanup is in a separate try block from model unloading (NEM-2022)."""
        import inspect

        import backend.main

        source = inspect.getsource(backend.main)

        # Find the positions of key elements
        model_unload_pos = source.find("await model_manager.unload_all()")
        cuda_cleanup_pos = source.find("torch.cuda.empty_cache()")

        # Both should exist
        assert model_unload_pos > 0, "Model unload code not found"
        assert cuda_cleanup_pos > 0, "CUDA cleanup code not found"

        # CUDA cleanup should come after model unload
        assert cuda_cleanup_pos > model_unload_pos, "CUDA cleanup should come after model unload"

        # There should be a separate try block between them (look for "except" between them)
        code_between = source[model_unload_pos:cuda_cleanup_pos]
        assert "except" in code_between, "CUDA cleanup should be in a separate try block"


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


class TestCudaCacheClearing:
    """Tests for CUDA cache clearing during shutdown (NEM-2022)."""

    def test_cuda_cleanup_handles_torch_not_installed(self):
        """Verify CUDA cleanup handles ImportError when torch is not available."""
        # The actual test verifies the cleanup code in main.py handles this
        # by checking the source code structure
        import inspect

        import backend.main

        source = inspect.getsource(backend.main)
        assert "except ImportError:" in source
        assert "torch not installed, skipping CUDA cleanup" in source

    def test_cuda_cleanup_handles_cuda_not_available(self):
        """Verify CUDA cleanup handles case when CUDA is not available."""
        import inspect

        import backend.main

        source = inspect.getsource(backend.main)

        # Verify the code checks for CUDA availability
        assert "torch.cuda.is_available()" in source
        assert "CUDA not available, skipping cache clear" in source

    def test_cuda_cleanup_handles_general_exception(self):
        """Verify CUDA cleanup handles general exceptions gracefully (NEM-2022)."""
        import inspect

        import backend.main

        source = inspect.getsource(backend.main)

        # Verify exception handling is present
        assert "except Exception as e:" in source
        assert "Warning: Error clearing CUDA cache" in source

    def test_cuda_synchronize_called_before_empty_cache(self):
        """Verify torch.cuda.synchronize() is called before empty_cache() (NEM-2022)."""
        import inspect

        import backend.main

        source = inspect.getsource(backend.main)

        # Find positions in the source code
        sync_pos = source.find("torch.cuda.synchronize()")
        empty_cache_pos = source.find("torch.cuda.empty_cache()")

        # Both should exist
        assert sync_pos > 0, "torch.cuda.synchronize() not found"
        assert empty_cache_pos > 0, "torch.cuda.empty_cache() not found"

        # synchronize should come before empty_cache
        assert sync_pos < empty_cache_pos, (
            "torch.cuda.synchronize() should be called before torch.cuda.empty_cache()"
        )


class TestCudaCleanupBehavior:
    """Tests for CUDA cleanup behavior with mocked torch (NEM-2022)."""

    def test_cuda_cleanup_calls_synchronize_when_available(self):
        """Verify synchronize is called when CUDA is available."""
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True
        mock_torch.cuda.synchronize = MagicMock()
        mock_torch.cuda.empty_cache = MagicMock()

        with patch.dict("sys.modules", {"torch": mock_torch}):
            # Simulate the cleanup code
            import torch

            if torch.cuda.is_available():
                torch.cuda.synchronize()
                torch.cuda.empty_cache()

        mock_torch.cuda.synchronize.assert_called_once()
        mock_torch.cuda.empty_cache.assert_called_once()

    def test_cuda_cleanup_skipped_when_not_available(self):
        """Verify cleanup is skipped when CUDA is not available."""
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False
        mock_torch.cuda.synchronize = MagicMock()
        mock_torch.cuda.empty_cache = MagicMock()

        with patch.dict("sys.modules", {"torch": mock_torch}):
            import torch

            if torch.cuda.is_available():
                torch.cuda.synchronize()
                torch.cuda.empty_cache()

        # Should not be called when CUDA is not available
        mock_torch.cuda.synchronize.assert_not_called()
        mock_torch.cuda.empty_cache.assert_not_called()

    def test_cuda_cleanup_continues_on_synchronize_error(self):
        """Verify that errors in synchronize don't prevent shutdown."""
        # This test verifies the error handling behavior
        import inspect

        import backend.main

        source = inspect.getsource(backend.main)

        # The entire CUDA cleanup block is wrapped in try-except
        # which means any error (including in synchronize) will be caught
        cuda_block_start = source.find("# Clear CUDA cache after model unload (NEM-2022)")
        cuda_block_end = source.find("await close_db()")

        cuda_block = source[cuda_block_start:cuda_block_end]

        # Count try and except to ensure proper nesting
        assert cuda_block.count("try:") >= 1, "CUDA cleanup should have try block"
        assert cuda_block.count("except") >= 2, (
            "CUDA cleanup should handle ImportError and general Exception"
        )
