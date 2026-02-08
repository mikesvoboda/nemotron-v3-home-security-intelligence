"""Integration tests for FastALPR loader (NEM-5569).

Tests verify model loading, availability detection, and graceful fallback.
"""

import pytest


@pytest.mark.integration
class TestFastALPRLoaderIntegration:
    """Integration tests for FastALPR model loader."""

    def test_availability_check(self) -> None:
        """Test that availability check works without fast-alpr installed."""
        from backend.services.fast_alpr_loader import _is_fast_alpr_available

        # Should return True or False without raising
        result = _is_fast_alpr_available()
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_load_raises_without_package(self) -> None:
        """Test graceful error when fast-alpr is not installed."""
        from backend.services.fast_alpr_loader import _is_fast_alpr_available

        if _is_fast_alpr_available():
            pytest.skip("fast-alpr is installed, cannot test missing package path")

        from backend.services.fast_alpr_loader import load_fast_alpr

        with pytest.raises(RuntimeError, match="not installed"):
            await load_fast_alpr()

    @pytest.mark.asyncio
    async def test_run_returns_empty_on_error(self) -> None:
        """Test that run_fast_alpr returns empty list on error."""
        from unittest.mock import MagicMock

        import numpy as np

        from backend.services.fast_alpr_loader import run_fast_alpr

        mock_alpr = MagicMock()
        mock_alpr.predict.side_effect = RuntimeError("test error")

        dummy_image = np.zeros((100, 100, 3), dtype=np.uint8)
        results = await run_fast_alpr(mock_alpr, dummy_image)
        assert results == []
