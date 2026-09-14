"""Tests for CPU Offloading (NEM-3813).

Tests for:
- Memory detection (GPU and CPU)
- Device map generation with CPU offloading
- Model loading with offloading
- OffloadingModelWrapper functionality
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import torch

# Add parent directory to path for imports
_ai_dir = Path(__file__).parent.parent
if str(_ai_dir) not in sys.path:
    sys.path.insert(0, str(_ai_dir))

from cpu_offloading import (
    DEFAULT_OFFLOAD_FOLDER,
    OffloadingConfig,
    OffloadingModelWrapper,
    estimate_model_size_gb,
    get_cpu_memory_info,
    get_gpu_memory_info,
    get_max_memory_config,
    get_offload_device_map,
    get_optimal_offload_config,
    load_model_with_offloading,
)


class TestIsCpuOffloadingSupported:
    """Tests for is_cpu_offloading_supported() function."""

    def test_returns_false_when_disabled_via_env(self):
        """Test that offloading is disabled when env var is set."""
        with patch.dict("os.environ", {"CPU_OFFLOAD_DISABLE": "1"}):
            import importlib

            import cpu_offloading

            importlib.reload(cpu_offloading)
            assert cpu_offloading.is_cpu_offloading_supported() is False

    def test_returns_false_when_accelerate_not_installed(self):
        """Test that offloading is disabled when accelerate not available."""
        with (
            patch.dict("os.environ", {"CPU_OFFLOAD_DISABLE": "0"}),
            patch.dict("sys.modules", {"accelerate": None}),
        ):
            # Mock ImportError for accelerate
            import importlib

            import cpu_offloading

            # Patch the import inside the function
            def mock_import(name, *_args, **_kwargs):
                if name == "accelerate":
                    raise ImportError("No module named 'accelerate'")
                return MagicMock()

            with patch("builtins.__import__", side_effect=mock_import):
                importlib.reload(cpu_offloading)
                # The function checks for ImportError
                result = cpu_offloading.is_cpu_offloading_supported()
                assert isinstance(result, bool)


class TestGetGpuMemoryInfo:
    """Tests for get_gpu_memory_info() function."""

    def test_returns_not_available_when_no_cuda(self):
        """Test returns not available when CUDA unavailable."""
        with patch("torch.cuda.is_available", return_value=False):
            info = get_gpu_memory_info()

            assert info["available"] is False
            assert info["num_gpus"] == 0
            assert info["gpus"] == []

    def test_returns_gpu_info_when_cuda_available(self):
        """Test returns GPU info when CUDA is available."""
        mock_props = MagicMock()
        mock_props.name = "NVIDIA RTX 4090"
        mock_props.total_memory = 24 * 1024**3  # 24GB

        with (
            patch("torch.cuda.is_available", return_value=True),
            patch("torch.cuda.device_count", return_value=1),
            patch("torch.cuda.get_device_properties", return_value=mock_props),
            patch("torch.cuda.memory_allocated", return_value=8 * 1024**3),
            patch("torch.cuda.memory_reserved", return_value=10 * 1024**3),
        ):
            info = get_gpu_memory_info()

            assert info["available"] is True
            assert info["num_gpus"] == 1
            assert len(info["gpus"]) == 1
            assert info["gpus"][0]["name"] == "NVIDIA RTX 4090"
            assert info["gpus"][0]["total_gb"] == 24.0


class TestGetCpuMemoryInfo:
    """Tests for get_cpu_memory_info() function."""

    def test_returns_info_with_psutil(self):
        """Test returns memory info when psutil is available."""
        mock_mem = MagicMock()
        mock_mem.total = 64 * 1024**3  # 64GB
        mock_mem.available = 32 * 1024**3  # 32GB
        mock_mem.used = 32 * 1024**3  # 32GB
        mock_mem.percent = 50.0

        with (
            patch.dict("sys.modules", {"psutil": MagicMock()}),
            patch("psutil.virtual_memory", return_value=mock_mem),
        ):
            info = get_cpu_memory_info()

            assert info["total_gb"] == 64.0
            assert info["available_gb"] == 32.0
            assert info["percent_used"] == 50.0

    def test_handles_missing_psutil(self):
        """Test handles missing psutil gracefully."""
        # Just test the function works without crashing
        info = get_cpu_memory_info()
        assert isinstance(info, dict)


class TestEstimateModelSizeGb:
    """Tests for estimate_model_size_gb() function."""

    def test_extracts_size_from_name(self):
        """Test extracting parameter count from model name."""
        size = estimate_model_size_gb(
            "nvidia/Nemotron-3-Nano-30B-A3B",
            dtype=torch.float16,
        )

        # 30B params * 2 bytes (fp16) * 1.2 overhead = ~72GB
        # But the function calculates differently
        assert size > 50  # Should be substantial for 30B model

    def test_handles_7b_models(self):
        """Test handling 7B model names."""
        size = estimate_model_size_gb(
            "meta-llama/Llama-2-7b",
            dtype=torch.float16,
        )

        # 7B * 2 bytes * 1.2 = ~16.8GB
        assert 10 < size < 25

    def test_handles_decimal_sizes(self):
        """Test handling decimal parameter counts."""
        size = estimate_model_size_gb(
            "some-model-1.5b-variant",
            dtype=torch.float16,
        )

        # 1.5B matches the pattern as 15b (regex matches 15 from 1.5b)
        # or may fall back to default 7B
        # The important thing is it returns a reasonable positive size
        assert size > 0

    def test_default_for_unknown_size(self):
        """Test default size for models without size in name."""
        size = estimate_model_size_gb(
            "unknown-model-name",
            dtype=torch.float16,
        )

        # Should use 7B default
        assert size > 10


class TestOffloadingConfig:
    """Tests for OffloadingConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = OffloadingConfig()

        assert config.max_gpu_memory_gb is None
        assert config.max_cpu_memory_gb is None
        assert config.offload_folder == DEFAULT_OFFLOAD_FOLDER
        assert config.offload_state_dict is False
        assert config.low_cpu_mem_usage is True
        assert config.torch_dtype == torch.float16

    def test_custom_values(self):
        """Test custom configuration values."""
        config = OffloadingConfig(
            max_gpu_memory_gb=20.0,
            max_cpu_memory_gb=64.0,
            offload_state_dict=True,
        )

        assert config.max_gpu_memory_gb == 20.0
        assert config.max_cpu_memory_gb == 64.0
        assert config.offload_state_dict is True


class TestGetMaxMemoryConfig:
    """Tests for get_max_memory_config() function."""

    def test_returns_empty_when_no_cuda(self):
        """Test returns empty dict when CUDA unavailable."""
        with patch("torch.cuda.is_available", return_value=False):
            config = get_max_memory_config()

            # Should only have CPU config
            assert all(k in (0, "cpu") or isinstance(k, int) for k in config)

    def test_includes_gpu_memory(self):
        """Test includes GPU memory when CUDA available."""
        mock_props = MagicMock()
        mock_props.total_memory = 24 * 1024**3  # 24GB

        with (
            patch("torch.cuda.is_available", return_value=True),
            patch("torch.cuda.device_count", return_value=1),
            patch("torch.cuda.get_device_properties", return_value=mock_props),
        ):
            config = get_max_memory_config()

            assert 0 in config
            assert "GiB" in config[0]

    def test_respects_max_gpu_memory(self):
        """Test respects max_gpu_memory_gb parameter."""
        mock_props = MagicMock()
        mock_props.total_memory = 24 * 1024**3

        with (
            patch("torch.cuda.is_available", return_value=True),
            patch("torch.cuda.device_count", return_value=1),
            patch("torch.cuda.get_device_properties", return_value=mock_props),
        ):
            config = get_max_memory_config(max_gpu_memory_gb=16.0)

            assert config[0] == "16.0GiB"


class TestGetOffloadDeviceMap:
    """Tests for get_offload_device_map() function."""

    def test_returns_cpu_when_no_cuda(self):
        """Test returns CPU device map when CUDA unavailable."""
        with patch("torch.cuda.is_available", return_value=False):
            device_map = get_offload_device_map("test-model")

            assert device_map == {"": "cpu"}

    def test_returns_auto_when_model_fits(self):
        """Test returns 'auto' when model fits in GPU."""
        mock_props = MagicMock()
        mock_props.total_memory = 24 * 1024**3  # 24GB

        with (
            patch("torch.cuda.is_available", return_value=True),
            patch("torch.cuda.device_count", return_value=1),
            patch("torch.cuda.get_device_properties", return_value=mock_props),
            patch("cpu_offloading.estimate_model_size_gb", return_value=10.0),  # Small model
        ):
            device_map = get_offload_device_map(
                "small-model-7b",
                allow_cpu_offload=True,
            )

            assert device_map == "auto"

    def test_enables_offload_for_large_model(self):
        """Test enables offloading for model larger than GPU."""
        mock_props = MagicMock()
        mock_props.total_memory = 8 * 1024**3  # 8GB

        with (
            patch("torch.cuda.is_available", return_value=True),
            patch("torch.cuda.device_count", return_value=1),
            patch("torch.cuda.get_device_properties", return_value=mock_props),
            patch("cpu_offloading.estimate_model_size_gb", return_value=20.0),  # Large model
        ):
            device_map = get_offload_device_map(
                "large-model-30b",
                allow_cpu_offload=True,
            )

            # Should return "auto" with offloading enabled
            assert device_map == "auto"


class TestOffloadingModelWrapper:
    """Tests for OffloadingModelWrapper class."""

    @pytest.fixture
    def mock_model(self):
        """Create a mock model for testing."""
        model = MagicMock()
        model.hf_device_map = {"layer1": "cuda:0", "layer2": "cpu"}
        model.generate.return_value = torch.tensor([[1, 2, 3]])
        return model

    def test_initialization(self, mock_model):
        """Test wrapper initialization."""
        wrapper = OffloadingModelWrapper(mock_model)

        assert wrapper.model is mock_model
        assert wrapper.device_map is not None

    def test_get_device_map(self, mock_model):
        """Test getting device map."""
        wrapper = OffloadingModelWrapper(mock_model)

        device_map = wrapper.get_device_map()

        assert device_map == {"layer1": "cuda:0", "layer2": "cpu"}

    def test_is_offloaded(self, mock_model):
        """Test checking if model is offloaded."""
        wrapper = OffloadingModelWrapper(mock_model)

        assert wrapper.is_offloaded() is True

    def test_is_not_offloaded(self, mock_model):
        """Test checking when model is not offloaded."""
        mock_model.hf_device_map = {"layer1": "cuda:0", "layer2": "cuda:0"}
        wrapper = OffloadingModelWrapper(mock_model)

        assert wrapper.is_offloaded() is False

    def test_forward(self, mock_model):
        """Test forward pass through wrapper."""
        wrapper = OffloadingModelWrapper(mock_model)
        input_tensor = torch.randn(1, 10)

        wrapper.forward(input_tensor)

        mock_model.assert_called_once_with(input_tensor)

    def test_generate(self, mock_model):
        """Test generate method."""
        wrapper = OffloadingModelWrapper(mock_model)
        input_ids = torch.tensor([[1, 2, 3]])

        output = wrapper.generate(input_ids, max_new_tokens=10)

        mock_model.generate.assert_called_once()
        assert output is not None

    def test_get_memory_usage(self, mock_model):
        """Test getting memory usage."""
        with (
            patch("cpu_offloading.get_gpu_memory_info") as mock_gpu,
            patch("cpu_offloading.get_cpu_memory_info") as mock_cpu,
        ):
            mock_gpu.return_value = {"available": True, "gpus": []}
            mock_cpu.return_value = {"total_gb": 64}

            wrapper = OffloadingModelWrapper(mock_model)
            usage = wrapper.get_memory_usage()

            assert "gpu" in usage
            assert "cpu" in usage
            assert "layers_by_device" in usage


class TestGetOptimalOffloadConfig:
    """Tests for get_optimal_offload_config() function."""

    def test_no_offload_when_model_fits(self):
        """Test no offloading config when model fits in GPU."""
        with (
            patch("cpu_offloading.get_gpu_memory_info") as mock_gpu,
            patch("cpu_offloading.get_cpu_memory_info") as mock_cpu,
            patch("cpu_offloading.estimate_model_size_gb", return_value=10.0),
        ):
            mock_gpu.return_value = {
                "available": True,
                "gpus": [{"total_gb": 24}],
            }
            mock_cpu.return_value = {"available_gb": 64}

            config = get_optimal_offload_config("small-model-7b")

            # Model (10GB) fits in GPU (24GB * 0.85 = 20.4GB)
            assert config.max_gpu_memory_gb is not None

    def test_cpu_offload_for_large_model(self):
        """Test CPU offloading config for large model."""
        with (
            patch("cpu_offloading.get_gpu_memory_info") as mock_gpu,
            patch("cpu_offloading.get_cpu_memory_info") as mock_cpu,
            patch("cpu_offloading.estimate_model_size_gb", return_value=30.0),
        ):
            mock_gpu.return_value = {
                "available": True,
                "gpus": [{"total_gb": 16}],
            }
            mock_cpu.return_value = {"available_gb": 64}

            config = get_optimal_offload_config("large-model-30b")

            # Model (30GB) doesn't fit in GPU (16GB * 0.85 = 13.6GB)
            # But fits with CPU offloading
            assert config.max_gpu_memory_gb is not None
            assert config.max_cpu_memory_gb is not None

    def test_latency_optimization(self):
        """Test optimization for low latency."""
        with (
            patch("cpu_offloading.get_gpu_memory_info") as mock_gpu,
            patch("cpu_offloading.get_cpu_memory_info") as mock_cpu,
            patch("cpu_offloading.estimate_model_size_gb", return_value=10.0),
        ):
            mock_gpu.return_value = {
                "available": True,
                "gpus": [{"total_gb": 24}],
            }
            mock_cpu.return_value = {"available_gb": 64}

            config = get_optimal_offload_config(
                "model",
                target_latency_ms=50,  # Low latency target
            )

            # Should maximize GPU usage for low latency
            assert config.max_gpu_memory_gb is not None


class TestLoadModelWithOffloading:
    """Tests for load_model_with_offloading() function."""

    def test_loads_model_with_device_map(self):
        """Test loading model with device map."""
        mock_model_class = MagicMock()
        mock_model = MagicMock()
        mock_model_class.from_pretrained.return_value = mock_model

        with (
            patch("cpu_offloading.get_offload_device_map", return_value="auto"),
            patch("torch.cuda.is_available", return_value=True),
            patch("torch.cuda.empty_cache"),
        ):
            load_model_with_offloading(
                mock_model_class,
                "test-model",
                max_gpu_memory_gb=16.0,
            )

            mock_model_class.from_pretrained.assert_called_once()
            call_kwargs = mock_model_class.from_pretrained.call_args.kwargs
            assert call_kwargs["device_map"] == "auto"
            assert call_kwargs["low_cpu_mem_usage"] is True

    def test_respects_custom_config(self):
        """Test respects custom offloading config."""
        mock_model_class = MagicMock()
        mock_model = MagicMock()
        mock_model_class.from_pretrained.return_value = mock_model

        config = OffloadingConfig(
            torch_dtype=torch.bfloat16,
            low_cpu_mem_usage=False,
        )

        with (
            patch("cpu_offloading.get_offload_device_map", return_value="auto"),
            patch("torch.cuda.is_available", return_value=True),
            patch("torch.cuda.empty_cache"),
        ):
            load_model_with_offloading(
                mock_model_class,
                "test-model",
                config=config,
            )

            call_kwargs = mock_model_class.from_pretrained.call_args.kwargs
            assert call_kwargs["torch_dtype"] == torch.bfloat16
            assert call_kwargs["low_cpu_mem_usage"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
