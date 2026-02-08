"""Integration tests for Zero-DCE++ loader (NEM-5567).

Tests verify model architecture, brightness detection, and enhancement behavior.
"""

import numpy as np
import pytest


@pytest.mark.integration
class TestZeroDCELoaderIntegration:
    """Integration tests for Zero-DCE++ model loader."""

    def test_should_enhance_dark_image(self) -> None:
        """Test brightness detection correctly identifies dark images."""
        from backend.services.zero_dce_loader import should_enhance

        # Create a dark image (mean luminance < 0.35)
        dark_image = np.zeros((100, 100, 3), dtype=np.uint8)
        dark_image[:] = 30  # Very dark
        assert should_enhance(dark_image) is True

    def test_should_not_enhance_bright_image(self) -> None:
        """Test brightness detection skips well-lit images."""
        from backend.services.zero_dce_loader import should_enhance

        # Create a bright image (mean luminance > 0.35)
        bright_image = np.ones((100, 100, 3), dtype=np.uint8) * 180
        assert should_enhance(bright_image) is False

    @pytest.mark.asyncio
    async def test_load_model_missing_weights(self) -> None:
        """Test graceful failure when model weights are missing."""
        from backend.services.zero_dce_loader import load_zero_dce_model

        with pytest.raises((RuntimeError, FileNotFoundError, OSError)):
            await load_zero_dce_model("/nonexistent/path")
