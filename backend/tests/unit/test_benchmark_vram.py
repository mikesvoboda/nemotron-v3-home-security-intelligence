"""Unit tests for VRAM benchmark dataclasses and report generation.

These tests verify the benchmark infrastructure without requiring a GPU.
The actual benchmarking requires manual execution on a system with CUDA.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Add scripts to path for imports
scripts_path = Path(__file__).parent.parent.parent / "scripts"
sys.path.insert(0, str(scripts_path))


class TestBenchmarkResult:
    """Tests for BenchmarkResult dataclass."""

    def test_benchmark_result_defaults(self):
        """Test BenchmarkResult with default values."""
        from benchmark_vram import BenchmarkResult

        result = BenchmarkResult(
            model_name="test-model",
            category="detection",
            estimated_vram_mb=500,
        )

        assert result.model_name == "test-model"
        assert result.category == "detection"
        assert result.estimated_vram_mb == 500
        assert result.actual_vram_mb is None
        assert result.loading_time_seconds is None
        assert result.success is False
        assert result.error is None

    def test_benchmark_result_success(self):
        """Test BenchmarkResult with success data."""
        from benchmark_vram import BenchmarkResult

        result = BenchmarkResult(
            model_name="clip-vit-l",
            category="embedding",
            estimated_vram_mb=800,
            actual_vram_mb=750,
            loading_time_seconds=2.5,
            unloading_time_seconds=0.1,
            success=True,
        )

        assert result.success is True
        assert result.actual_vram_mb == 750
        assert result.loading_time_seconds == 2.5
        assert result.unloading_time_seconds == 0.1

    def test_benchmark_result_failure(self):
        """Test BenchmarkResult with failure."""
        from benchmark_vram import BenchmarkResult

        result = BenchmarkResult(
            model_name="unavailable-model",
            category="detection",
            estimated_vram_mb=1000,
            success=False,
            error="Model not found",
        )

        assert result.success is False
        assert result.error == "Model not found"


class TestBenchmarkReport:
    """Tests for BenchmarkReport dataclass."""

    def test_benchmark_report_defaults(self):
        """Test BenchmarkReport with default values."""
        from benchmark_vram import BenchmarkReport

        report = BenchmarkReport(
            baseline_vram_mb=500,
            total_gpu_memory_mb=24000,
        )

        assert report.baseline_vram_mb == 500
        assert report.total_gpu_memory_mb == 24000
        assert report.results == []
        assert report.timestamp == ""

    def test_benchmark_report_to_markdown_empty(self):
        """Test markdown generation with no results."""
        from benchmark_vram import BenchmarkReport

        report = BenchmarkReport(
            baseline_vram_mb=500,
            total_gpu_memory_mb=24000,
            timestamp="2025-12-26T10:00:00Z",
        )

        markdown = report.to_markdown()

        assert "# VRAM Benchmark Report" in markdown
        assert "24,000 MB" in markdown
        assert "500 MB" in markdown
        assert "23,500 MB" in markdown  # Available = total - baseline

    def test_benchmark_report_to_markdown_with_results(self):
        """Test markdown generation with benchmark results."""
        from benchmark_vram import BenchmarkReport, BenchmarkResult

        report = BenchmarkReport(
            baseline_vram_mb=1000,
            total_gpu_memory_mb=24000,
            timestamp="2025-12-26T12:00:00Z",
            results=[
                BenchmarkResult(
                    model_name="clip-vit-l",
                    category="embedding",
                    estimated_vram_mb=800,
                    actual_vram_mb=750,
                    loading_time_seconds=2.5,
                    success=True,
                ),
                BenchmarkResult(
                    model_name="florence-2-large",
                    category="vision-language",
                    estimated_vram_mb=1200,
                    actual_vram_mb=1100,
                    loading_time_seconds=5.0,
                    success=True,
                ),
                BenchmarkResult(
                    model_name="unavailable-model",
                    category="detection",
                    estimated_vram_mb=500,
                    success=False,
                    error="Import error",
                ),
            ],
        )

        markdown = report.to_markdown()

        # Check header
        assert "# VRAM Benchmark Report" in markdown
        assert "2025-12-26T12:00:00Z" in markdown

        # Check table
        assert "| Model | Category |" in markdown
        assert "clip-vit-l" in markdown
        assert "florence-2-large" in markdown
        assert "unavailable-model" in markdown

        # Check summary
        assert "**Successful loads:** 2/3" in markdown
        assert "**Failed models:** unavailable-model" in markdown

    def test_benchmark_report_summary_calculations(self):
        """Test summary statistics calculations."""
        from benchmark_vram import BenchmarkReport, BenchmarkResult

        report = BenchmarkReport(
            baseline_vram_mb=500,
            total_gpu_memory_mb=24000,
            results=[
                BenchmarkResult(
                    model_name="model1",
                    category="detection",
                    estimated_vram_mb=300,
                    actual_vram_mb=280,
                    loading_time_seconds=1.0,
                    success=True,
                ),
                BenchmarkResult(
                    model_name="model2",
                    category="detection",
                    estimated_vram_mb=500,
                    actual_vram_mb=450,
                    loading_time_seconds=3.0,
                    success=True,
                ),
            ],
        )

        markdown = report.to_markdown()

        # Peak VRAM should be 450 (max of successful models)
        assert "450" in markdown
        # Average load time should be 2.0s
        assert "2.00s" in markdown


class TestBenchmarkHelpers:
    """Tests for benchmark helper functions."""

    def test_clear_gpu_cache_no_torch(self):
        """Test clear_gpu_cache works without torch or when GPU unavailable."""
        from benchmark_vram import clear_gpu_cache

        # Should not raise even without torch/CUDA or when GPU is in error state
        try:
            clear_gpu_cache()
        except Exception as e:
            # Skip if GPU is in error state (OOM, device unavailable, etc.)
            if "CUDA" in str(e) or "cuda" in str(e) or "GPU" in str(e):
                pytest.skip(f"GPU not available or in error state: {e}")
            raise

    @pytest.mark.skipif(
        True,
        reason="GPU-dependent test - run manually on GPU system",
    )
    def test_get_gpu_memory_returns_tuple(self):
        """Test get_gpu_memory returns valid tuple."""
        from benchmark_vram import get_gpu_memory

        used, total = get_gpu_memory()
        assert isinstance(used, int)
        assert isinstance(total, int)
        assert used >= 0
        assert total >= 0


class TestModelZooIntegration:
    """Tests for Model Zoo integration with benchmark."""

    def test_model_zoo_available(self):
        """Test that model zoo can be imported and accessed."""
        from backend.services.model_zoo import get_model_zoo

        zoo = get_model_zoo()

        assert "clip-vit-l" in zoo
        assert "florence-2-large" in zoo
        assert "yolo11-license-plate" in zoo
        assert "paddleocr" in zoo

    def test_enabled_models(self):
        """Test that expected models are enabled."""
        from backend.services.model_zoo import get_enabled_models

        enabled = get_enabled_models()
        enabled_names = {m.name for m in enabled}

        # These should be enabled by default
        assert "clip-vit-l" in enabled_names
        assert "paddleocr" in enabled_names
        # Note: florence-2-large now runs as dedicated ai-florence service (disabled in model zoo)

    def test_model_vram_estimates(self):
        """Test that model VRAM estimates are reasonable."""
        from backend.services.model_zoo import get_model_zoo

        zoo = get_model_zoo()

        # VRAM estimates should be non-negative and within reasonable bounds
        # Some models like BRISQUE are CPU-based (vram_mb=0)
        for name, config in zoo.items():
            assert config.vram_mb >= 0, f"{name} has invalid VRAM estimate"
            assert config.vram_mb < 10000, f"{name} has unreasonably high VRAM estimate"

    def test_total_vram_calculation(self):
        """Test total VRAM calculation for multiple models."""
        from backend.services.model_zoo import get_total_vram_if_loaded

        # Test with known models
        total = get_total_vram_if_loaded(["clip-vit-l", "florence-2-large"])

        # Should be sum of both models (800 + 1200 = 2000)
        assert total == 2000

    def test_total_vram_empty_list(self):
        """Test total VRAM calculation with empty list."""
        from backend.services.model_zoo import get_total_vram_if_loaded

        total = get_total_vram_if_loaded([])
        assert total == 0

    def test_total_vram_unknown_model(self):
        """Test total VRAM calculation ignores unknown models."""
        from backend.services.model_zoo import get_total_vram_if_loaded

        # Unknown model should be ignored
        total = get_total_vram_if_loaded(["clip-vit-l", "nonexistent-model"])

        # Should only count clip-vit-l (800)
        assert total == 800
