"""TDD tests for Phase 3: Quantization Exploration.

Tests for quantization comparison benchmarking:
- VRAM measurement for each quantization format
- Quality delta calculation
- Loading and running inference with different formats
- VRAM savings vs quality loss tracking
- Edge cases (aggressive quantization, corruption)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestQuantizationConfig:
    """Tests for quantization configuration."""

    def test_config_has_required_formats(self) -> None:
        """Test that config includes all quantization formats to benchmark."""
        from scripts.benchmark.quantization_comparison import QUANTIZATION_FORMATS

        expected_formats = ["Q4_K_M", "Q4_K_S", "Q3_K_M", "Q3_K_S", "Q2_K_L"]
        for fmt in expected_formats:
            assert fmt in QUANTIZATION_FORMATS, f"Missing format: {fmt}"

    def test_config_has_model_paths(self) -> None:
        """Test that config maps formats to model file paths."""
        from scripts.benchmark.quantization_comparison import get_model_path

        path = get_model_path("Q4_K_M")
        assert path is not None
        assert isinstance(path, Path)

    def test_config_invalid_format_raises_error(self) -> None:
        """Test that invalid format raises ValueError."""
        from scripts.benchmark.quantization_comparison import get_model_path

        with pytest.raises(ValueError, match="Unknown quantization format"):
            get_model_path("INVALID_FORMAT")

    def test_baseline_format_defined(self) -> None:
        """Test that baseline quantization format is defined."""
        from scripts.benchmark.quantization_comparison import BASELINE_FORMAT

        assert BASELINE_FORMAT in ["Q4_K_M", "Q4_K_S"]


class TestVRAMCapture:
    """Tests for VRAM measurement per quantization format."""

    @pytest.mark.asyncio
    async def test_capture_vram_during_inference(self) -> None:
        """Test that VRAM is captured during model inference."""
        from scripts.benchmark.quantization_comparison import capture_vram_metrics

        with (
            patch(
                "scripts.benchmark.quantization_comparison.run_nvidia_smi",
                new_callable=AsyncMock,
            ) as mock_smi,
        ):
            mock_smi.return_value = 8192.0  # 8GB VRAM
            metrics = await capture_vram_metrics(duration_sec=1.0)

            assert "peak_mb" in metrics
            assert "steady_state_mb" in metrics
            assert metrics["peak_mb"] >= 0

    @pytest.mark.asyncio
    async def test_vram_measurement_during_load(self) -> None:
        """Test VRAM measurement captures peak during model load."""
        from scripts.benchmark.quantization_comparison import (
            QuantizationBenchmarker,
        )

        benchmarker = QuantizationBenchmarker(service_url="http://localhost:8091")

        with (
            patch.object(benchmarker, "_load_model", new_callable=AsyncMock),
            patch.object(
                benchmarker,
                "_capture_vram",
                new_callable=AsyncMock,
                return_value={"peak_mb": 12000.0, "steady_state_mb": 10000.0},
            ),
        ):
            vram = await benchmarker.measure_vram_for_format("Q4_K_M")
            assert vram["peak_mb"] == 12000.0

    @pytest.mark.asyncio
    async def test_vram_measurement_returns_float(self) -> None:
        """Test that VRAM values are returned as floats."""
        from scripts.benchmark.quantization_comparison import capture_vram_metrics

        with patch(
            "scripts.benchmark.quantization_comparison.run_nvidia_smi",
            new_callable=AsyncMock,
            return_value=4096.5,
        ):
            metrics = await capture_vram_metrics(duration_sec=0.1)
            assert isinstance(metrics["peak_mb"], float)


class TestQualityDeltaCalculation:
    """Tests for quality delta calculation between formats."""

    def test_quality_delta_exact_match(self) -> None:
        """Test quality delta is 0 for identical scores."""
        from scripts.benchmark.quantization_comparison import calculate_quality_delta

        delta = calculate_quality_delta(baseline=0.95, test=0.95)
        assert delta == 0.0

    def test_quality_delta_improvement(self) -> None:
        """Test positive delta when test is better."""
        from scripts.benchmark.quantization_comparison import calculate_quality_delta

        delta = calculate_quality_delta(baseline=0.90, test=0.95)
        assert delta > 0

    def test_quality_delta_regression(self) -> None:
        """Test negative delta when test is worse."""
        from scripts.benchmark.quantization_comparison import calculate_quality_delta

        delta = calculate_quality_delta(baseline=0.95, test=0.85)
        assert delta < 0

    def test_quality_delta_percentage_format(self) -> None:
        """Test quality delta is expressed as percentage points."""
        from scripts.benchmark.quantization_comparison import calculate_quality_delta

        # 95% to 90% is -5 percentage points
        delta = calculate_quality_delta(baseline=0.95, test=0.90)
        assert abs(delta - (-5.0)) < 0.01

    def test_quality_delta_zero_baseline_raises(self) -> None:
        """Test that zero baseline quality raises error."""
        from scripts.benchmark.quantization_comparison import calculate_quality_delta

        with pytest.raises(ValueError, match="Baseline quality cannot be zero"):
            calculate_quality_delta(baseline=0.0, test=0.5)


class TestVRAMSavingsCalculation:
    """Tests for VRAM savings calculation."""

    def test_vram_savings_calculation(self) -> None:
        """Test VRAM savings percentage calculation."""
        from scripts.benchmark.quantization_comparison import calculate_vram_savings

        # 12000 MB to 8000 MB is 33.3% savings
        savings = calculate_vram_savings(baseline_mb=12000, test_mb=8000)
        assert abs(savings - 33.33) < 0.1

    def test_vram_savings_no_change(self) -> None:
        """Test VRAM savings is 0 when equal."""
        from scripts.benchmark.quantization_comparison import calculate_vram_savings

        savings = calculate_vram_savings(baseline_mb=10000, test_mb=10000)
        assert savings == 0.0

    def test_vram_increase_shows_negative_savings(self) -> None:
        """Test that VRAM increase shows as negative savings."""
        from scripts.benchmark.quantization_comparison import calculate_vram_savings

        savings = calculate_vram_savings(baseline_mb=8000, test_mb=12000)
        assert savings < 0  # Negative savings = increase


class TestQuantizationBenchmarker:
    """Tests for the main quantization benchmarker class."""

    def test_benchmarker_initialization(self) -> None:
        """Test benchmarker initializes correctly."""
        from scripts.benchmark.quantization_comparison import QuantizationBenchmarker

        benchmarker = QuantizationBenchmarker(service_url="http://localhost:8091")
        assert benchmarker.service_url == "http://localhost:8091"

    def test_benchmarker_accepts_model_path(self) -> None:
        """Test benchmarker can be initialized with custom model path."""
        from scripts.benchmark.quantization_comparison import QuantizationBenchmarker

        benchmarker = QuantizationBenchmarker(
            service_url="http://localhost:8091",
            model_base_path=Path("/models/nemotron"),
        )
        assert benchmarker.model_base_path == Path("/models/nemotron")

    @pytest.mark.asyncio
    async def test_benchmark_single_format(self) -> None:
        """Test benchmarking a single quantization format."""
        from scripts.benchmark.quantization_comparison import QuantizationBenchmarker

        benchmarker = QuantizationBenchmarker(service_url="http://localhost:8091")

        with (
            patch.object(
                benchmarker,
                "_run_inference_benchmark",
                new_callable=AsyncMock,
                return_value={
                    "latency_p50_ms": 1200.0,
                    "tokens_per_sec": 25.0,
                    "quality_score": 0.92,
                },
            ),
            patch.object(
                benchmarker,
                "_capture_vram",
                new_callable=AsyncMock,
                return_value={"peak_mb": 10000.0, "steady_state_mb": 9500.0},
            ),
        ):
            result = await benchmarker.benchmark_format("Q4_K_M")

            assert "format" in result
            assert result["format"] == "Q4_K_M"
            assert "vram" in result
            assert "latency_p50_ms" in result
            assert "quality_score" in result

    @pytest.mark.asyncio
    async def test_benchmark_all_formats(self) -> None:
        """Test benchmarking all quantization formats."""
        from scripts.benchmark.quantization_comparison import QuantizationBenchmarker

        benchmarker = QuantizationBenchmarker(service_url="http://localhost:8091")

        mock_result = {
            "format": "Q4_K_M",
            "vram": {"peak_mb": 10000.0},
            "latency_p50_ms": 1200.0,
            "quality_score": 0.92,
        }

        with patch.object(
            benchmarker,
            "benchmark_format",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            results = await benchmarker.benchmark_all_formats()

            assert isinstance(results, list)
            assert len(results) > 0


class TestInferenceBenchmark:
    """Tests for inference benchmarking per quantization format."""

    @pytest.mark.asyncio
    async def test_inference_returns_latency(self) -> None:
        """Test that inference benchmark returns latency metrics."""
        from scripts.benchmark.quantization_comparison import QuantizationBenchmarker

        benchmarker = QuantizationBenchmarker(service_url="http://localhost:8091")

        with patch(
            "scripts.benchmark.quantization_comparison.httpx.AsyncClient"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "response": "Test response",
                "total_time_ms": 1500.0,
            }
            mock_response.raise_for_status = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await benchmarker._run_inference_benchmark("Q4_K_M", num_requests=1)

            assert "latency_p50_ms" in result

    @pytest.mark.asyncio
    async def test_inference_returns_throughput(self) -> None:
        """Test that inference benchmark returns throughput metrics."""
        from scripts.benchmark.quantization_comparison import QuantizationBenchmarker

        benchmarker = QuantizationBenchmarker(service_url="http://localhost:8091")

        with patch.object(
            benchmarker,
            "_send_inference_request",
            new_callable=AsyncMock,
            return_value={"total_time_ms": 1000.0, "tokens": 50},
        ):
            result = await benchmarker._run_inference_benchmark("Q4_K_M", num_requests=5)

            assert "tokens_per_sec" in result


class TestQualityMeasurement:
    """Tests for quality measurement during benchmarking."""

    @pytest.mark.asyncio
    async def test_quality_score_captured(self) -> None:
        """Test that quality score is captured for each format."""
        from scripts.benchmark.quantization_comparison import QuantizationBenchmarker

        benchmarker = QuantizationBenchmarker(service_url="http://localhost:8091")

        with patch.object(
            benchmarker,
            "_evaluate_quality",
            new_callable=AsyncMock,
            return_value=0.93,
        ):
            quality = await benchmarker._measure_quality("Q4_K_M")
            assert 0 <= quality <= 1

    @pytest.mark.asyncio
    async def test_quality_uses_evaluation_set(self) -> None:
        """Test that quality measurement uses the evaluation set."""
        from scripts.benchmark.quantization_comparison import QuantizationBenchmarker

        benchmarker = QuantizationBenchmarker(
            service_url="http://localhost:8091",
            evaluation_set_path=Path("data/benchmark/evaluation-set"),
        )

        with (
            patch.object(benchmarker, "_load_evaluation_set", return_value=[{"prompt": "test"}]),
            patch.object(
                benchmarker,
                "_run_evaluation",
                new_callable=AsyncMock,
                return_value=0.95,
            ),
        ):
            quality = await benchmarker._measure_quality("Q4_K_M")
            assert quality == 0.95


class TestComparisonResults:
    """Tests for comparison result generation."""

    def test_comparison_includes_all_formats(self) -> None:
        """Test that comparison includes all benchmark formats."""
        from scripts.benchmark.quantization_comparison import generate_comparison_results

        benchmark_results = [
            {"format": "Q4_K_M", "vram": {"peak_mb": 12000}, "quality_score": 0.95},
            {"format": "Q3_K_M", "vram": {"peak_mb": 9000}, "quality_score": 0.90},
        ]

        comparison = generate_comparison_results(benchmark_results, baseline="Q4_K_M")

        assert len(comparison["formats"]) == 2
        assert "Q4_K_M" in [r["format"] for r in comparison["formats"]]
        assert "Q3_K_M" in [r["format"] for r in comparison["formats"]]

    def test_comparison_calculates_relative_metrics(self) -> None:
        """Test that comparison calculates VRAM savings vs quality delta."""
        from scripts.benchmark.quantization_comparison import generate_comparison_results

        benchmark_results = [
            {"format": "Q4_K_M", "vram": {"peak_mb": 12000}, "quality_score": 0.95},
            {"format": "Q3_K_M", "vram": {"peak_mb": 9000}, "quality_score": 0.90},
        ]

        comparison = generate_comparison_results(benchmark_results, baseline="Q4_K_M")

        q3_result = next(r for r in comparison["formats"] if r["format"] == "Q3_K_M")
        assert "vram_savings_pct" in q3_result
        assert "quality_delta_pct" in q3_result

    def test_comparison_baseline_has_zero_deltas(self) -> None:
        """Test that baseline format shows 0% for savings and delta."""
        from scripts.benchmark.quantization_comparison import generate_comparison_results

        benchmark_results = [
            {"format": "Q4_K_M", "vram": {"peak_mb": 12000}, "quality_score": 0.95},
        ]

        comparison = generate_comparison_results(benchmark_results, baseline="Q4_K_M")

        baseline_result = comparison["formats"][0]
        assert baseline_result["vram_savings_pct"] == 0.0
        assert baseline_result["quality_delta_pct"] == 0.0


class TestEdgeCases:
    """Tests for edge cases in quantization benchmarking."""

    @pytest.mark.asyncio
    async def test_aggressive_quantization_detection(self) -> None:
        """Test detection of gibberish output from over-quantized model."""
        from scripts.benchmark.quantization_comparison import (
            detect_gibberish_output,
        )

        # Gibberish output has no coherent words
        gibberish = "asdf qwer zxcv bnm hjkl"
        assert detect_gibberish_output(gibberish) is True

        # Coherent output
        normal = "The security camera detected motion at the front door."
        assert detect_gibberish_output(normal) is False

    @pytest.mark.asyncio
    async def test_model_load_failure_handling(self) -> None:
        """Test handling when model fails to load."""
        from scripts.benchmark.quantization_comparison import QuantizationBenchmarker

        benchmarker = QuantizationBenchmarker(service_url="http://localhost:8091")

        with (
            patch.object(
                benchmarker,
                "_load_model",
                new_callable=AsyncMock,
                side_effect=RuntimeError("Model file corrupted"),
            ),
            pytest.raises(RuntimeError, match="Model file corrupted"),
        ):
            await benchmarker.benchmark_format("Q2_K_L")

    @pytest.mark.asyncio
    async def test_quality_below_threshold_flagged(self) -> None:
        """Test that quality below 95% of baseline is flagged."""
        from scripts.benchmark.quantization_comparison import (
            is_quality_acceptable,
        )

        # 85% quality when baseline is 95% = 89.5% of baseline (below 95% threshold)
        assert is_quality_acceptable(test=0.85, baseline=0.95, threshold=0.95) is False

        # 93% quality when baseline is 95% = 97.9% of baseline (above 95% threshold)
        assert is_quality_acceptable(test=0.93, baseline=0.95, threshold=0.95) is True

    def test_missing_vram_data_handled(self) -> None:
        """Test handling when VRAM data is missing."""
        from scripts.benchmark.quantization_comparison import generate_comparison_results

        benchmark_results = [
            {"format": "Q4_K_M", "vram": None, "quality_score": 0.95},
        ]

        comparison = generate_comparison_results(benchmark_results, baseline="Q4_K_M")

        assert comparison["formats"][0]["vram_savings_pct"] is None


class TestReportGeneration:
    """Tests for markdown report generation."""

    def test_generate_markdown_report(self) -> None:
        """Test markdown report generation."""
        from scripts.benchmark.quantization_comparison import generate_markdown_report

        comparison = {
            "baseline": "Q4_K_M",
            "formats": [
                {
                    "format": "Q4_K_M",
                    "vram_peak_mb": 12000,
                    "quality_score": 0.95,
                    "vram_savings_pct": 0.0,
                    "quality_delta_pct": 0.0,
                },
                {
                    "format": "Q3_K_M",
                    "vram_peak_mb": 9000,
                    "quality_score": 0.90,
                    "vram_savings_pct": 25.0,
                    "quality_delta_pct": -5.26,
                },
            ],
        }

        report = generate_markdown_report(comparison)

        assert "# Quantization Comparison Report" in report
        assert "Q4_K_M" in report
        assert "Q3_K_M" in report
        assert "VRAM" in report

    def test_report_includes_recommendation(self) -> None:
        """Test that report includes recommended quantization."""
        from scripts.benchmark.quantization_comparison import generate_markdown_report

        comparison = {
            "baseline": "Q4_K_M",
            "recommended": "Q3_K_M",
            "formats": [
                {
                    "format": "Q3_K_M",
                    "vram_peak_mb": 9000,
                    "quality_score": 0.93,
                    "vram_savings_pct": 25.0,
                    "quality_delta_pct": -2.1,
                    "acceptable": True,
                },
            ],
        }

        report = generate_markdown_report(comparison)

        assert "Recommended" in report or "recommended" in report.lower()

    def test_report_saved_to_file(self, tmp_path: Path) -> None:
        """Test that report can be saved to file."""
        from scripts.benchmark.quantization_comparison import save_comparison_report

        comparison = {
            "baseline": "Q4_K_M",
            "formats": [],
        }

        output_file = tmp_path / "quantization-comparison.md"
        save_comparison_report(comparison, output_file)

        assert output_file.exists()
        content = output_file.read_text()
        assert "Quantization" in content


class TestCLIInterface:
    """Tests for CLI interface."""

    def test_parse_args_formats(self) -> None:
        """Test parsing --formats argument."""
        from scripts.benchmark.quantization_comparison import parse_args

        args = parse_args(["--formats", "Q4_K_M", "Q3_K_M"])
        assert args.formats == ["Q4_K_M", "Q3_K_M"]

    def test_parse_args_output(self) -> None:
        """Test parsing --output argument."""
        from scripts.benchmark.quantization_comparison import parse_args

        args = parse_args(["--output", "results/comparison.md"])
        assert args.output == Path("results/comparison.md")

    def test_parse_args_baseline(self) -> None:
        """Test parsing --baseline argument."""
        from scripts.benchmark.quantization_comparison import parse_args

        args = parse_args(["--baseline", "Q4_K_M"])
        assert args.baseline == "Q4_K_M"

    def test_parse_args_service_url(self) -> None:
        """Test parsing --service-url argument."""
        from scripts.benchmark.quantization_comparison import parse_args

        args = parse_args(["--service-url", "http://localhost:9000"])
        assert args.service_url == "http://localhost:9000"


class TestIntegrationScenarios:
    """Integration tests for end-to-end quantization comparison."""

    @pytest.fixture
    def mock_benchmark_results(self) -> list[dict[str, Any]]:
        """Create mock benchmark results for all formats."""
        return [
            {
                "format": "Q4_K_M",
                "vram": {"peak_mb": 12000.0, "steady_state_mb": 11500.0},
                "latency_p50_ms": 1200.0,
                "latency_p95_ms": 1800.0,
                "tokens_per_sec": 25.0,
                "quality_score": 0.95,
            },
            {
                "format": "Q4_K_S",
                "vram": {"peak_mb": 11000.0, "steady_state_mb": 10500.0},
                "latency_p50_ms": 1100.0,
                "latency_p95_ms": 1700.0,
                "tokens_per_sec": 27.0,
                "quality_score": 0.94,
            },
            {
                "format": "Q3_K_M",
                "vram": {"peak_mb": 9000.0, "steady_state_mb": 8500.0},
                "latency_p50_ms": 900.0,
                "latency_p95_ms": 1400.0,
                "tokens_per_sec": 32.0,
                "quality_score": 0.91,
            },
            {
                "format": "Q3_K_S",
                "vram": {"peak_mb": 8500.0, "steady_state_mb": 8000.0},
                "latency_p50_ms": 850.0,
                "latency_p95_ms": 1300.0,
                "tokens_per_sec": 35.0,
                "quality_score": 0.88,
            },
            {
                "format": "Q2_K_L",
                "vram": {"peak_mb": 7000.0, "steady_state_mb": 6500.0},
                "latency_p50_ms": 700.0,
                "latency_p95_ms": 1100.0,
                "tokens_per_sec": 40.0,
                "quality_score": 0.80,
            },
        ]

    @pytest.mark.asyncio
    async def test_full_comparison_workflow(
        self, mock_benchmark_results: list[dict[str, Any]], tmp_path: Path
    ) -> None:
        """Test complete quantization comparison workflow."""
        from scripts.benchmark.quantization_comparison import (
            generate_comparison_results,
            save_comparison_report,
        )

        # Generate comparison
        comparison = generate_comparison_results(mock_benchmark_results, baseline="Q4_K_M")

        # Verify comparison structure
        assert comparison["baseline"] == "Q4_K_M"
        assert len(comparison["formats"]) == 5

        # Save report
        output_file = tmp_path / "comparison.md"
        save_comparison_report(comparison, output_file)

        assert output_file.exists()

    def test_vram_quality_tradeoff_curve(
        self, mock_benchmark_results: list[dict[str, Any]]
    ) -> None:
        """Test generation of VRAM vs quality tradeoff data."""
        from scripts.benchmark.quantization_comparison import (
            generate_comparison_results,
            get_tradeoff_curve_data,
        )

        comparison = generate_comparison_results(mock_benchmark_results, baseline="Q4_K_M")
        tradeoff_data = get_tradeoff_curve_data(comparison)

        # Verify tradeoff data structure
        assert "vram_savings" in tradeoff_data
        assert "quality_loss" in tradeoff_data
        assert "formats" in tradeoff_data
        assert len(tradeoff_data["formats"]) == 5

    def test_recommendation_selection(self, mock_benchmark_results: list[dict[str, Any]]) -> None:
        """Test that recommendation selects optimal format."""
        from scripts.benchmark.quantization_comparison import (
            generate_comparison_results,
            select_recommended_format,
        )

        comparison = generate_comparison_results(mock_benchmark_results, baseline="Q4_K_M")

        # Select format with best VRAM savings while maintaining 95% quality
        recommended = select_recommended_format(
            comparison, quality_threshold=0.95, vram_target_mb=10000
        )

        # Should recommend a format that fits in VRAM and meets quality
        assert recommended is not None
        assert recommended["quality_score"] >= 0.95 * 0.95
