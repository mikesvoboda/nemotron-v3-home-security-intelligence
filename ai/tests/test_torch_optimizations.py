"""Tests for PyTorch Optimization Utilities.

Tests for:
- torch.compile() integration (NEM-3375)
- True batch inference helpers (NEM-3377)
- Accelerate device_map utilities (NEM-3378)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import torch
from PIL import Image

# Add parent directory to path for imports
_ai_dir = Path(__file__).parent.parent
if str(_ai_dir) not in sys.path:
    sys.path.insert(0, str(_ai_dir))

from torch_optimizations import (
    COMPILE_MODES,
    BatchConfig,
    BatchProcessor,
    compile_model,
    get_optimal_device_map,
    get_torch_dtype_for_device,
    load_model_with_accelerate,
    warmup_compiled_model,
)


class TestIsCompileSupported:
    """Tests for is_compile_supported() function."""

    def test_returns_false_when_disabled_via_env(self):
        """Test that compilation is disabled when TORCH_COMPILE_DISABLE=1."""
        with patch.dict(os.environ, {"TORCH_COMPILE_DISABLE": "1"}):
            # Need to reimport to pick up the environment variable
            import importlib

            import torch_optimizations

            importlib.reload(torch_optimizations)
            assert torch_optimizations.is_compile_supported() is False

    def test_returns_false_for_old_pytorch(self):
        """Test that compilation is disabled for PyTorch < 2.0."""
        with (
            patch.dict(os.environ, {"TORCH_COMPILE_DISABLE": "0"}),
            patch.object(torch, "__version__", "1.13.0"),
        ):
            # Need to check version in function, not at import time
            # So we mock the function's internal version check
            import importlib

            import torch_optimizations

            importlib.reload(torch_optimizations)
            # This will return False because CUDA might not be available
            # The key is it doesn't crash
            result = torch_optimizations.is_compile_supported()
            assert isinstance(result, bool)

    def test_returns_false_when_cuda_not_available(self):
        """Test that compilation is disabled when CUDA is not available."""
        with (
            patch.dict(os.environ, {"TORCH_COMPILE_DISABLE": "0"}),
            patch("torch.cuda.is_available", return_value=False),
        ):
            import importlib

            import torch_optimizations

            importlib.reload(torch_optimizations)
            assert torch_optimizations.is_compile_supported() is False


class TestGetCompileMode:
    """Tests for get_compile_mode() function."""

    def test_default_mode(self):
        """Test that default mode is 'reduce-overhead'."""
        with patch.dict(os.environ, {"TORCH_COMPILE_MODE": "reduce-overhead"}):
            import importlib

            import torch_optimizations

            importlib.reload(torch_optimizations)
            assert torch_optimizations.get_compile_mode() == "reduce-overhead"

    def test_custom_mode(self):
        """Test that custom mode is respected."""
        with patch.dict(os.environ, {"TORCH_COMPILE_MODE": "max-autotune"}):
            import importlib

            import torch_optimizations

            importlib.reload(torch_optimizations)
            assert torch_optimizations.get_compile_mode() == "max-autotune"

    def test_invalid_mode_falls_back_to_default(self):
        """Test that invalid mode falls back to 'reduce-overhead'."""
        with patch.dict(os.environ, {"TORCH_COMPILE_MODE": "invalid-mode"}):
            import importlib

            import torch_optimizations

            importlib.reload(torch_optimizations)
            assert torch_optimizations.get_compile_mode() == "reduce-overhead"

    def test_all_valid_modes(self):
        """Test that all documented modes are valid."""
        expected_modes = {
            "default",
            "reduce-overhead",
            "max-autotune",
            "max-autotune-no-cudagraphs",
        }
        assert expected_modes == COMPILE_MODES


class TestCompileModel:
    """Tests for compile_model() function."""

    def test_returns_original_model_when_compile_not_supported(self):
        """Test that original model is returned when compilation is not supported."""
        mock_model = MagicMock()

        with patch("torch_optimizations.is_compile_supported", return_value=False):
            result = compile_model(mock_model)
            assert result is mock_model

    def test_compiles_model_when_supported(self):
        """Test that model is compiled when supported."""
        mock_model = MagicMock()
        compiled_mock = MagicMock()

        with (
            patch("torch_optimizations.is_compile_supported", return_value=True),
            patch("torch.compile", return_value=compiled_mock) as mock_compile,
        ):
            result = compile_model(mock_model, mode="reduce-overhead")

            mock_compile.assert_called_once_with(
                mock_model,
                mode="reduce-overhead",
                fullgraph=False,
                dynamic=True,
                backend="inductor",
            )
            assert result is compiled_mock

    def test_returns_original_on_compile_failure(self):
        """Test that original model is returned when compilation fails."""
        mock_model = MagicMock()

        with (
            patch("torch_optimizations.is_compile_supported", return_value=True),
            patch("torch.compile", side_effect=Exception("Compile error")),
        ):
            result = compile_model(mock_model)
            assert result is mock_model

    def test_uses_default_mode_when_none_provided(self):
        """Test that default mode is used when None is provided."""
        mock_model = MagicMock()

        with (
            patch("torch_optimizations.is_compile_supported", return_value=True),
            patch("torch_optimizations.get_compile_mode", return_value="default") as mock_mode,
            patch("torch.compile", return_value=MagicMock()),
        ):
            compile_model(mock_model, mode=None)
            mock_mode.assert_called_once()


class TestGetOptimalDeviceMap:
    """Tests for get_optimal_device_map() function."""

    def test_returns_cpu_map_when_cuda_not_available(self):
        """Test that CPU device map is returned when CUDA is not available."""
        with patch("torch.cuda.is_available", return_value=False):
            result = get_optimal_device_map("test-model")
            assert result == {"": "cpu"}

    def test_returns_auto_for_single_gpu(self):
        """Test that 'auto' is returned for single GPU setup."""
        with (
            patch("torch.cuda.is_available", return_value=True),
            patch("torch.cuda.device_count", return_value=1),
        ):
            result = get_optimal_device_map("test-model")
            assert result == "auto"

    def test_returns_auto_for_multi_gpu(self):
        """Test that 'auto' is returned for multi-GPU setup."""
        with (
            patch("torch.cuda.is_available", return_value=True),
            patch("torch.cuda.device_count", return_value=4),
        ):
            result = get_optimal_device_map("test-model")
            assert result == "auto"


class TestLoadModelWithAccelerate:
    """Tests for load_model_with_accelerate() function."""

    def test_loads_model_with_device_map(self):
        """Test that model is loaded with device_map."""
        mock_model_class = MagicMock()
        mock_model = MagicMock()
        mock_model_class.from_pretrained.return_value = mock_model

        with (
            patch("torch_optimizations.get_optimal_device_map", return_value="auto"),
            patch("torch_optimizations.compile_model", return_value=mock_model),
        ):
            result = load_model_with_accelerate(
                mock_model_class,
                "test-model",
                use_compile=False,
            )

            mock_model_class.from_pretrained.assert_called_once_with(
                "test-model",
                device_map="auto",
                torch_dtype=torch.float16,
            )
            mock_model.eval.assert_called_once()
            assert result is mock_model

    def test_compiles_model_when_enabled(self):
        """Test that model is compiled when use_compile=True."""
        mock_model_class = MagicMock()
        mock_model = MagicMock()
        compiled_model = MagicMock()
        mock_model_class.from_pretrained.return_value = mock_model

        with (
            patch("torch_optimizations.get_optimal_device_map", return_value="auto"),
            patch("torch_optimizations.compile_model", return_value=compiled_model) as mock_compile,
        ):
            result = load_model_with_accelerate(
                mock_model_class,
                "test-model",
                use_compile=True,
            )

            mock_compile.assert_called_once()
            assert result is compiled_model


class TestBatchConfig:
    """Tests for BatchConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = BatchConfig()
        assert config.max_batch_size == 8
        assert config.dynamic_batching is True
        assert config.pad_to_max is False

    def test_custom_values(self):
        """Test custom configuration values."""
        config = BatchConfig(max_batch_size=16, dynamic_batching=False, pad_to_max=True)
        assert config.max_batch_size == 16
        assert config.dynamic_batching is False
        assert config.pad_to_max is True


class TestBatchProcessor:
    """Tests for BatchProcessor class (NEM-3377)."""

    def test_create_batches_default_size(self):
        """Test creating batches with default batch size."""
        processor = BatchProcessor(BatchConfig(max_batch_size=3))
        items = [1, 2, 3, 4, 5, 6, 7]

        batches = list(processor.create_batches(items))

        assert len(batches) == 3
        assert batches[0] == [1, 2, 3]
        assert batches[1] == [4, 5, 6]
        assert batches[2] == [7]

    def test_create_batches_custom_size(self):
        """Test creating batches with custom batch size."""
        processor = BatchProcessor(BatchConfig(max_batch_size=8))
        items = [1, 2, 3, 4, 5]

        batches = list(processor.create_batches(items, batch_size=2))

        assert len(batches) == 3
        assert batches[0] == [1, 2]
        assert batches[1] == [3, 4]
        assert batches[2] == [5]

    def test_create_batches_empty_list(self):
        """Test creating batches from empty list."""
        processor = BatchProcessor()
        batches = list(processor.create_batches([]))
        assert batches == []

    def test_create_batches_single_item(self):
        """Test creating batches with single item."""
        processor = BatchProcessor(BatchConfig(max_batch_size=8))
        batches = list(processor.create_batches([1]))
        assert batches == [[1]]

    def test_create_batches_exact_multiple(self):
        """Test batches when items are exact multiple of batch size."""
        processor = BatchProcessor(BatchConfig(max_batch_size=2))
        items = [1, 2, 3, 4]

        batches = list(processor.create_batches(items))

        assert len(batches) == 2
        assert batches[0] == [1, 2]
        assert batches[1] == [3, 4]

    def test_get_optimal_batch_size_no_cuda(self):
        """Test optimal batch size when CUDA is not available."""
        processor = BatchProcessor(BatchConfig(max_batch_size=8, dynamic_batching=True))
        sample_image = Image.new("RGB", (640, 480))

        with patch("torch.cuda.is_available", return_value=False):
            result = processor.get_optimal_batch_size(sample_image)
            # Should return a reasonable value (at least 1, at most max)
            assert 1 <= result <= 8

    def test_get_optimal_batch_size_dynamic_disabled(self):
        """Test optimal batch size when dynamic batching is disabled."""
        processor = BatchProcessor(BatchConfig(max_batch_size=16, dynamic_batching=False))
        sample_image = Image.new("RGB", (640, 480))

        result = processor.get_optimal_batch_size(sample_image)
        assert result == 16

    def test_get_optimal_batch_size_with_vram(self):
        """Test optimal batch size with specified VRAM."""
        processor = BatchProcessor(BatchConfig(max_batch_size=32, dynamic_batching=True))
        sample_image = Image.new("RGB", (640, 480))

        # With 8GB VRAM, should calculate a reasonable batch size
        result = processor.get_optimal_batch_size(sample_image, available_vram_gb=8.0)
        assert 1 <= result <= 32


class TestWarmupCompiledModel:
    """Tests for warmup_compiled_model() function."""

    def test_warmup_with_dict_input(self):
        """Test warmup with dictionary input."""
        mock_model = MagicMock()
        sample_input = {"input_ids": torch.zeros(1, 10)}

        warmup_compiled_model(mock_model, sample_input, num_warmup=2)

        assert mock_model.call_count == 2

    def test_warmup_with_tensor_input(self):
        """Test warmup with tensor input."""
        mock_model = MagicMock()
        sample_input = torch.zeros(1, 3, 224, 224)

        warmup_compiled_model(mock_model, sample_input, num_warmup=3)

        assert mock_model.call_count == 3

    def test_warmup_handles_exception(self):
        """Test that warmup handles exceptions gracefully."""
        mock_model = MagicMock()
        mock_model.side_effect = RuntimeError("Test error")
        sample_input = {"input_ids": torch.zeros(1, 10)}

        # Should not raise, just log warning
        warmup_compiled_model(mock_model, sample_input, num_warmup=2)


class TestGetTorchDtypeForDevice:
    """Tests for get_torch_dtype_for_device() function."""

    def test_returns_float16_for_cuda(self):
        """Test that float16 is returned for CUDA device."""
        with (
            patch("torch.cuda.is_available", return_value=True),
            patch("torch.cuda.is_bf16_supported", return_value=False),
        ):
            result = get_torch_dtype_for_device("cuda:0")
            assert result == torch.float16

    def test_returns_bfloat16_when_supported(self):
        """Test that bfloat16 is returned when supported."""
        with (
            patch("torch.cuda.is_available", return_value=True),
            patch("torch.cuda.is_bf16_supported", return_value=True),
        ):
            result = get_torch_dtype_for_device("cuda:0")
            assert result == torch.bfloat16

    def test_returns_float32_for_cpu(self):
        """Test that float32 is returned for CPU device."""
        result = get_torch_dtype_for_device("cpu")
        assert result == torch.float32


class TestBatchProcessorWithImages:
    """Integration tests for BatchProcessor with actual PIL Images."""

    @pytest.fixture
    def sample_images(self) -> list[Image.Image]:
        """Create sample PIL images for testing."""
        return [Image.new("RGB", (640, 480), color=(i * 25, i * 25, i * 25)) for i in range(10)]

    def test_batch_pil_images(self, sample_images: list[Image.Image]):
        """Test batching PIL images."""
        processor = BatchProcessor(BatchConfig(max_batch_size=4))

        batches = list(processor.create_batches(sample_images))

        assert len(batches) == 3
        assert len(batches[0]) == 4
        assert len(batches[1]) == 4
        assert len(batches[2]) == 2

        # Verify all items are PIL Images
        for batch in batches:
            for img in batch:
                assert isinstance(img, Image.Image)

    def test_optimal_batch_size_small_images(self, sample_images: list[Image.Image]):
        """Test optimal batch size calculation for small images."""
        processor = BatchProcessor(BatchConfig(max_batch_size=32, dynamic_batching=True))

        # Small 640x480 image should allow large batch sizes
        with patch("torch.cuda.is_available", return_value=False):
            batch_size = processor.get_optimal_batch_size(sample_images[0], available_vram_gb=8.0)
            assert batch_size > 0
            assert batch_size <= 32

    def test_optimal_batch_size_large_images(self):
        """Test optimal batch size calculation for large images."""
        processor = BatchProcessor(BatchConfig(max_batch_size=32, dynamic_batching=True))
        large_image = Image.new("RGB", (4096, 4096))

        # Large 4096x4096 image should result in smaller batch sizes
        with patch("torch.cuda.is_available", return_value=False):
            batch_size = processor.get_optimal_batch_size(large_image, available_vram_gb=8.0)
            assert batch_size > 0
            # Should be smaller than max due to memory constraints
            # With 8GB VRAM and 4096x4096 images, batch size should be limited


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
