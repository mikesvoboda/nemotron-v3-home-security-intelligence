"""Integration tests for Zero-DCE++ loader (NEM-5567).

Tests verify model architecture, brightness detection, and enhancement behavior.
"""

import numpy as np
import pytest


@pytest.mark.integration
class TestZeroDCELoaderIntegration:
    """Integration tests for Zero-DCE++ model loader."""

    def test_should_enhance_dark_image(self) -> None:
        """Test brightness detection correctly identifies dark images.

        should_enhance takes a PIL Image (zero_dce_loader.py:163 —
        image.mode/.convert), not an ndarray. (ledger R-T9-ZERODCE)
        """
        from PIL import Image

        from backend.services.zero_dce_loader import should_enhance

        # Create a dark image (mean luminance 30/255 ≈ 0.12 < 0.35)
        dark = np.zeros((100, 100, 3), dtype=np.uint8)
        dark[:] = 30
        assert should_enhance(Image.fromarray(dark)) is True

    def test_should_not_enhance_bright_image(self) -> None:
        """Test brightness detection skips well-lit images."""
        from PIL import Image

        from backend.services.zero_dce_loader import should_enhance

        # Create a bright image (mean luminance > 0.35)
        bright_image = Image.fromarray(np.ones((100, 100, 3), dtype=np.uint8) * 180)
        assert should_enhance(bright_image) is False

    @pytest.mark.asyncio
    async def test_load_model_missing_weights(self) -> None:
        """Test graceful failure when model weights are missing."""
        from backend.services.zero_dce_loader import load_zero_dce_model

        with pytest.raises((RuntimeError, FileNotFoundError, OSError)):
            await load_zero_dce_model("/nonexistent/path")
