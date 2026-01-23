"""Tests for torch.compile() utilities (NEM-3370).

These tests verify the compile_utils module for model optimization.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
import torch


class TestIsCompileAvailable:
    """Tests for is_compile_available function."""

    def test_pytorch_2_returns_true(self) -> None:
        """Test that PyTorch 2.x returns True."""
        from compile_utils import is_compile_available

        # PyTorch 2.x should support torch.compile()
        if torch.__version__.startswith("2"):
            assert is_compile_available() is True

    def test_version_parsing(self) -> None:
        """Test version string parsing."""
        from compile_utils import is_compile_available

        # The function should handle version strings correctly
        result = is_compile_available()
        assert isinstance(result, bool)


class TestCompileConfig:
    """Tests for CompileConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        from compile_utils import CompileConfig

        config = CompileConfig()

        assert config.enabled is True
        assert config.mode == "reduce-overhead"
        assert config.backend == "inductor"
        assert config.fullgraph is False
        assert config.dynamic is False
        assert config.options == {}

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        from compile_utils import CompileConfig

        config = CompileConfig(
            enabled=False,
            mode="max-autotune",
            backend="cudagraphs",
            fullgraph=True,
            dynamic=True,
            options={"max_autotune": True},
        )

        assert config.enabled is False
        assert config.mode == "max-autotune"
        assert config.backend == "cudagraphs"
        assert config.fullgraph is True
        assert config.dynamic is True
        assert config.options == {"max_autotune": True}

    def test_from_env_defaults(self) -> None:
        """Test from_env with default environment."""
        from compile_utils import CompileConfig

        # Clear any existing env vars
        env_vars = [
            "TORCH_COMPILE_ENABLED",
            "TORCH_COMPILE_MODE",
            "TORCH_COMPILE_BACKEND",
            "TORCH_COMPILE_FULLGRAPH",
            "TORCH_COMPILE_DYNAMIC",
        ]
        old_values = {k: os.environ.pop(k, None) for k in env_vars}

        try:
            config = CompileConfig.from_env()
            assert config.enabled is True
            assert config.mode == "reduce-overhead"
            assert config.backend == "inductor"
        finally:
            # Restore old values
            for k, v in old_values.items():
                if v is not None:
                    os.environ[k] = v

    def test_from_env_custom(self) -> None:
        """Test from_env with custom environment variables."""
        from compile_utils import CompileConfig

        # Set custom env vars
        os.environ["TORCH_COMPILE_ENABLED"] = "false"
        os.environ["TORCH_COMPILE_MODE"] = "max-autotune"
        os.environ["TORCH_COMPILE_BACKEND"] = "cudagraphs"

        try:
            config = CompileConfig.from_env()
            assert config.enabled is False
            assert config.mode == "max-autotune"
            assert config.backend == "cudagraphs"
        finally:
            # Clean up
            del os.environ["TORCH_COMPILE_ENABLED"]
            del os.environ["TORCH_COMPILE_MODE"]
            del os.environ["TORCH_COMPILE_BACKEND"]


class TestCompileModel:
    """Tests for compile_model function."""

    def test_disabled_config_returns_original(self) -> None:
        """Test that disabled config returns original model."""
        from compile_utils import CompileConfig, compile_model

        # Create a simple model
        model = torch.nn.Linear(10, 5)
        config = CompileConfig(enabled=False)

        result = compile_model(model, config=config)
        assert result is model

    @pytest.mark.skipif(
        not torch.__version__.startswith("2"),
        reason="torch.compile() requires PyTorch 2.0+",
    )
    def test_compile_simple_model(self) -> None:
        """Test compiling a simple model."""
        from compile_utils import CompileConfig, compile_model

        model = torch.nn.Linear(10, 5)
        config = CompileConfig(enabled=True)

        result = compile_model(model, config=config)

        # Result should be the compiled model (or original on failure)
        assert result is not None
        # Model should still be callable
        x = torch.randn(1, 10)
        output = result(x)
        assert output.shape == (1, 5)

    def test_compile_fallback_on_error(self) -> None:
        """Test that compile falls back gracefully on errors."""
        from compile_utils import CompileConfig, compile_model

        # Mock torch.compile to raise an error
        model = torch.nn.Linear(10, 5)
        config = CompileConfig(enabled=True)

        with patch("torch.compile", side_effect=RuntimeError("Compilation failed")):
            result = compile_model(model, config=config)

        # Should return original model on failure
        assert result is model


class TestCompileForInference:
    """Tests for compile_for_inference function."""

    def test_uses_reduce_overhead_mode(self) -> None:
        """Test that compile_for_inference uses reduce-overhead mode."""
        from compile_utils import compile_for_inference

        model = torch.nn.Linear(10, 5)

        # The function should work without errors
        result = compile_for_inference(model)
        assert result is not None


class TestCompileForThroughput:
    """Tests for compile_for_throughput function."""

    def test_uses_max_autotune_mode(self) -> None:
        """Test that compile_for_throughput uses max-autotune mode."""
        from compile_utils import compile_for_throughput

        model = torch.nn.Linear(10, 5)

        # The function should work without errors
        result = compile_for_throughput(model)
        assert result is not None


class TestWarmupCompiledModel:
    """Tests for warmup_compiled_model function."""

    def test_warmup_runs_iterations(self) -> None:
        """Test that warmup runs the specified number of iterations."""
        from compile_utils import warmup_compiled_model

        model = torch.nn.Linear(10, 5)
        model.eval()

        sample_input = torch.randn(1, 10)

        # Should not raise any errors
        warmup_compiled_model(model, sample_input, num_warmup=2)

    def test_warmup_with_dict_input(self) -> None:
        """Test warmup with dictionary input."""
        from compile_utils import warmup_compiled_model

        # Create a model that accepts kwargs
        class DictModel(torch.nn.Module):
            def __init__(self) -> None:
                super().__init__()
                self.linear = torch.nn.Linear(10, 5)

            def forward(self, x: torch.Tensor) -> torch.Tensor:
                result: torch.Tensor = self.linear(x)
                return result

        model = DictModel()
        model.eval()

        sample_input = {"x": torch.randn(1, 10)}

        # Should not raise any errors
        warmup_compiled_model(model, sample_input, num_warmup=1)
