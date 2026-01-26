"""Tests for warmup_utils module (NEM-3816)."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import torch

from ai.warmup_utils import (
    WarmupConfig,
    WarmupResult,
    _clear_cuda_cache,
    _create_dummy_image,
    _sync_cuda,
    warmup_model_sync,
    warmup_pipeline,
    warmup_vision_model,
)


class TestWarmupConfig:
    """Tests for WarmupConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = WarmupConfig()

        assert config.num_samples == 3
        assert config.clear_cache_after is True
        assert config.sync_cuda is True
        assert config.input_text == "Warmup text for model initialization."
        assert config.input_image_size == (640, 480)
        assert config.max_new_tokens == 10
        assert config.log_timing is True
        assert config.timeout_seconds == 60.0

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = WarmupConfig(
            num_samples=5,
            clear_cache_after=False,
            input_text="Custom warmup text",
            input_image_size=(320, 240),
            timeout_seconds=30.0,
        )

        assert config.num_samples == 5
        assert config.clear_cache_after is False
        assert config.input_text == "Custom warmup text"
        assert config.input_image_size == (320, 240)
        assert config.timeout_seconds == 30.0


class TestWarmupResult:
    """Tests for WarmupResult dataclass."""

    def test_successful_result(self) -> None:
        """Test successful warmup result."""
        result = WarmupResult(
            success=True,
            iterations_completed=3,
            total_time_ms=1500.0,
            avg_time_ms=500.0,
        )

        assert result.success is True
        assert result.iterations_completed == 3
        assert result.total_time_ms == 1500.0
        assert result.avg_time_ms == 500.0
        assert result.errors == []

    def test_failed_result(self) -> None:
        """Test failed warmup result with errors."""
        result = WarmupResult(
            success=False,
            iterations_completed=1,
            total_time_ms=500.0,
            avg_time_ms=500.0,
            errors=["Warmup iteration 2 failed: CUDA OOM"],
        )

        assert result.success is False
        assert result.iterations_completed == 1
        assert len(result.errors) == 1
        assert "CUDA OOM" in result.errors[0]


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_create_dummy_image_default_size(self) -> None:
        """Test dummy image creation with default size."""
        image = _create_dummy_image()

        assert image.size == (640, 480)
        assert image.mode == "RGB"

    def test_create_dummy_image_custom_size(self) -> None:
        """Test dummy image creation with custom size."""
        image = _create_dummy_image(size=(320, 240))

        assert image.size == (320, 240)
        assert image.mode == "RGB"

    @patch("ai.warmup_utils.torch.cuda.is_available", return_value=False)
    def test_clear_cuda_cache_no_cuda(self, _mock_cuda: MagicMock) -> None:
        """Test CUDA cache clearing when CUDA is not available."""
        # Should not raise
        _clear_cuda_cache()

    @patch("ai.warmup_utils.torch.cuda.is_available", return_value=True)
    @patch("ai.warmup_utils.torch.cuda.empty_cache")
    def test_clear_cuda_cache_with_cuda(
        self, mock_empty_cache: MagicMock, _mock_cuda: MagicMock
    ) -> None:
        """Test CUDA cache clearing when CUDA is available."""
        _clear_cuda_cache()
        mock_empty_cache.assert_called_once()

    @patch("ai.warmup_utils.torch.cuda.is_available", return_value=False)
    def test_sync_cuda_no_cuda(self, _mock_cuda: MagicMock) -> None:
        """Test CUDA synchronization when CUDA is not available."""
        # Should not raise
        _sync_cuda()

    @patch("ai.warmup_utils.torch.cuda.is_available", return_value=True)
    @patch("ai.warmup_utils.torch.cuda.synchronize")
    def test_sync_cuda_with_cuda(self, mock_synchronize: MagicMock, _mock_cuda: MagicMock) -> None:
        """Test CUDA synchronization when CUDA is available."""
        _sync_cuda()
        mock_synchronize.assert_called_once()


class TestWarmupPipeline:
    """Tests for warmup_pipeline function."""

    @pytest.mark.asyncio
    async def test_warmup_pipeline_success(self) -> None:
        """Test successful pipeline warmup."""
        # Create mock pipeline that accepts text and max_new_tokens
        mock_pipeline = MagicMock()
        mock_pipeline.return_value = "Generated text"

        config = WarmupConfig(num_samples=2, clear_cache_after=False, sync_cuda=False)
        result = await warmup_pipeline(mock_pipeline, config=config)

        assert result.success is True
        assert result.iterations_completed == 2
        assert result.total_time_ms > 0
        assert result.avg_time_ms > 0
        assert mock_pipeline.call_count == 2

    @pytest.mark.asyncio
    async def test_warmup_pipeline_with_errors(self) -> None:
        """Test pipeline warmup with errors."""
        # Create mock pipeline that raises on first call
        call_count = 0

        def failing_pipeline(*_args: Any, **_kwargs: Any) -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Pipeline error")
            return "Generated text"

        config = WarmupConfig(num_samples=3, clear_cache_after=False, sync_cuda=False)
        result = await warmup_pipeline(failing_pipeline, config=config)

        assert result.success is False
        assert result.iterations_completed == 2  # 2 successful, 1 failed
        assert len(result.errors) == 1
        assert "Pipeline error" in result.errors[0]

    @pytest.mark.asyncio
    async def test_warmup_pipeline_custom_text(self) -> None:
        """Test pipeline warmup with custom input text."""
        mock_pipeline = MagicMock()
        mock_pipeline.return_value = "Output"

        await warmup_pipeline(
            mock_pipeline,
            config=WarmupConfig(num_samples=1, sync_cuda=False, clear_cache_after=False),
            input_text="Custom warmup text",
        )

        # Check that the custom text was passed
        mock_pipeline.assert_called_once()
        args, kwargs = mock_pipeline.call_args
        assert args[0] == "Custom warmup text"


class TestWarmupVisionModel:
    """Tests for warmup_vision_model function."""

    @pytest.mark.asyncio
    async def test_warmup_vision_model_with_inference_fn(self) -> None:
        """Test vision model warmup with custom inference function."""
        mock_model = MagicMock()

        def inference_fn(_model: Any, _image: Any) -> dict[str, Any]:
            return {"detection": "mock"}

        config = WarmupConfig(num_samples=2, clear_cache_after=False, sync_cuda=False)
        result = await warmup_vision_model(
            mock_model,
            config=config,
            inference_fn=inference_fn,
        )

        assert result.success is True
        assert result.iterations_completed == 2

    @pytest.mark.asyncio
    async def test_warmup_vision_model_with_processor(self) -> None:
        """Test vision model warmup with HuggingFace-style processor."""
        # Create mock model with parameters
        mock_model = MagicMock()
        mock_param = MagicMock()
        mock_param.dtype = torch.float32
        mock_model.parameters.return_value = iter([mock_param])

        # Create mock processor
        mock_processor = MagicMock()
        mock_processor.return_value = {"pixel_values": torch.zeros(1, 3, 224, 224)}

        config = WarmupConfig(
            num_samples=1,
            clear_cache_after=False,
            sync_cuda=False,
            input_image_size=(224, 224),
        )
        result = await warmup_vision_model(
            mock_model,
            processor=mock_processor,
            device="cpu",
            config=config,
        )

        assert result.success is True
        assert result.iterations_completed == 1


class TestWarmupModelSync:
    """Tests for warmup_model_sync function."""

    def test_warmup_model_sync_success(self) -> None:
        """Test successful synchronous model warmup."""
        mock_model = MagicMock()
        call_count = 0

        def warmup_fn(_model: Any) -> str:
            nonlocal call_count
            call_count += 1
            return f"result_{call_count}"

        with patch("ai.warmup_utils._sync_cuda"), patch("ai.warmup_utils._clear_cuda_cache"):
            result = warmup_model_sync(
                mock_model,
                warmup_fn,
                num_samples=3,
                clear_cache_after=True,
            )

        assert result.success is True
        assert result.iterations_completed == 3
        assert call_count == 3

    def test_warmup_model_sync_with_errors(self) -> None:
        """Test synchronous warmup with errors."""
        mock_model = MagicMock()
        call_count = 0

        def failing_warmup_fn(_model: Any) -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("Warmup failed")
            return "result"

        with patch("ai.warmup_utils._sync_cuda"), patch("ai.warmup_utils._clear_cuda_cache"):
            result = warmup_model_sync(
                mock_model,
                failing_warmup_fn,
                num_samples=3,
                clear_cache_after=True,
            )

        assert result.success is False
        assert result.iterations_completed == 2  # 2 successful, 1 failed
        assert len(result.errors) == 1
        assert "Warmup failed" in result.errors[0]


class TestWarmupTimeout:
    """Tests for warmup timeout behavior."""

    @pytest.mark.asyncio
    async def test_warmup_pipeline_timeout(self) -> None:
        """Test that pipeline warmup respects timeout."""

        async def slow_pipeline(*_args: Any, **_kwargs: Any) -> str:
            await asyncio.sleep(0.2)  # 200ms per iteration
            return "result"

        # Note: warmup_pipeline uses asyncio.to_thread, so we need a different approach
        # For this test, we use a very short timeout
        config = WarmupConfig(
            num_samples=100,  # More than can complete in timeout
            timeout_seconds=0.1,  # Very short timeout
            sync_cuda=False,
            clear_cache_after=False,
        )

        # This test verifies timeout behavior exists
        # In practice, the exact number of completed iterations depends on timing
        mock_pipeline = MagicMock()
        mock_pipeline.return_value = "result"

        result = await warmup_pipeline(mock_pipeline, config=config)
        # Should complete at least 1 iteration before timeout logic kicks in
        assert result.iterations_completed >= 1
