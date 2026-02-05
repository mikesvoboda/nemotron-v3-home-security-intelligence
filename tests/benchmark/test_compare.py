"""Test suite for benchmark comparison tool (TDD red phase).

This module tests the benchmark comparison functionality that loads benchmark
result JSON files, calculates deltas, and generates markdown comparison tables.

Test Coverage:
- JSON result file loading and validation
- Delta calculation between baseline and test runs
- Markdown table generation with formatting
- Improvement/regression highlighting (↑↓ symbols)
- Missing metrics handling
- CLI interface and argument parsing
- Multiple benchmark file comparison
- Edge cases (empty results, invalid data, missing files)

Following TDD principles:
1. Tests written first (RED phase)
2. Tests should FAIL initially
3. Implementation will make tests pass (GREEN phase)
4. Refactor after tests pass (REFACTOR phase)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


class TestBenchmarkResultLoader:
    """Test loading and parsing benchmark result JSON files."""

    def test_load_single_benchmark_file(self, tmp_path: Path) -> None:
        """Test loading a valid benchmark result JSON file."""
        from scripts.benchmark.compare import BenchmarkComparer

        # Create sample benchmark result
        result_data = {
            "model_name": "nemotron-70b-Q4_K_M",
            "timestamp": "2026-02-05T10:30:00",
            "metrics": {
                "latency": {
                    "p50_ms": 39600,
                    "p95_ms": 42100,
                    "p99_ms": 43800,
                    "mean_ms": 39800,
                },
                "throughput": {
                    "requests_per_min": 1.51,
                    "tokens_per_sec": 12.4,
                },
                "vram": {
                    "peak_mb": 14700,
                    "steady_state_mb": 14200,
                },
                "quality": {
                    "accuracy_pct": 100.0,
                    "risk_level_match_pct": 100.0,
                },
            },
        }

        result_file = tmp_path / "baseline.json"
        result_file.write_text(json.dumps(result_data, indent=2))

        comparer = BenchmarkComparer()
        result = comparer.load_benchmark_result(result_file)

        assert result["model_name"] == "nemotron-70b-Q4_K_M"
        assert result["metrics"]["latency"]["p50_ms"] == 39600
        assert result["metrics"]["vram"]["peak_mb"] == 14700

    def test_load_missing_file_raises_error(self) -> None:
        """Test that loading a non-existent file raises appropriate error."""
        from scripts.benchmark.compare import BenchmarkComparer

        comparer = BenchmarkComparer()

        with pytest.raises(FileNotFoundError, match="Benchmark result file not found"):
            comparer.load_benchmark_result(Path("/nonexistent/file.json"))

    def test_load_invalid_json_raises_error(self, tmp_path: Path) -> None:
        """Test that invalid JSON raises appropriate error."""
        from scripts.benchmark.compare import BenchmarkComparer

        invalid_file = tmp_path / "invalid.json"
        invalid_file.write_text("{ invalid json content")

        comparer = BenchmarkComparer()

        with pytest.raises(ValueError, match="Invalid JSON"):
            comparer.load_benchmark_result(invalid_file)

    def test_load_missing_required_fields_raises_error(self, tmp_path: Path) -> None:
        """Test that missing required fields raises validation error."""
        from scripts.benchmark.compare import BenchmarkComparer

        incomplete_data = {
            "model_name": "test-model",
            # Missing metrics
        }

        result_file = tmp_path / "incomplete.json"
        result_file.write_text(json.dumps(incomplete_data))

        comparer = BenchmarkComparer()

        with pytest.raises(ValueError, match="Missing required field"):
            comparer.load_benchmark_result(result_file)


class TestDeltaCalculation:
    """Test delta calculation between baseline and test runs."""

    def test_calculate_percentage_delta_decrease(self) -> None:
        """Test percentage delta calculation for a decrease (improvement)."""
        from scripts.benchmark.compare import calculate_percentage_delta

        baseline = 39600  # ms
        test = 32100  # ms

        delta = calculate_percentage_delta(baseline, test)

        assert delta == pytest.approx(-18.94, abs=0.01)  # -19% improvement

    def test_calculate_percentage_delta_increase(self) -> None:
        """Test percentage delta calculation for an increase (regression)."""
        from scripts.benchmark.compare import calculate_percentage_delta

        baseline = 100.0  # accuracy %
        test = 96.2  # accuracy %

        delta = calculate_percentage_delta(baseline, test)

        assert delta == pytest.approx(-3.8, abs=0.01)  # -3.8% regression

    def test_calculate_percentage_delta_zero_baseline(self) -> None:
        """Test that zero baseline raises appropriate error."""
        from scripts.benchmark.compare import calculate_percentage_delta

        with pytest.raises(ValueError, match="Baseline value cannot be zero"):
            calculate_percentage_delta(0, 50)

    def test_calculate_percentage_delta_negative_values(self) -> None:
        """Test delta calculation with negative values."""
        from scripts.benchmark.compare import calculate_percentage_delta

        baseline = -100
        test = -80

        delta = calculate_percentage_delta(baseline, test)

        assert delta == pytest.approx(20.0, abs=0.01)

    def test_calculate_latency_deltas(self) -> None:
        """Test calculating deltas for all latency metrics."""
        from scripts.benchmark.compare import BenchmarkComparer

        baseline = {
            "latency": {
                "p50_ms": 39600,
                "p95_ms": 42100,
                "p99_ms": 43800,
            }
        }

        test = {
            "latency": {
                "p50_ms": 32100,
                "p95_ms": 34500,
                "p99_ms": 36200,
            }
        }

        comparer = BenchmarkComparer()
        deltas = comparer.calculate_metric_deltas(baseline, test, "latency")

        assert deltas["p50_ms"] == pytest.approx(-18.94, abs=0.01)
        assert deltas["p95_ms"] == pytest.approx(-18.05, abs=0.01)
        assert deltas["p99_ms"] == pytest.approx(-17.35, abs=0.01)


class TestMarkdownTableGeneration:
    """Test markdown table generation for comparison reports."""

    def test_generate_latency_comparison_table(self) -> None:
        """Test generating markdown table for latency comparison."""
        from scripts.benchmark.compare import BenchmarkComparer

        baseline_data = {
            "model_name": "Q4_K_M",
            "metrics": {
                "latency": {
                    "p50_ms": 39600,
                    "p95_ms": 42100,
                    "p99_ms": 43800,
                }
            },
        }

        test_data = {
            "model_name": "Q3_K_M",
            "metrics": {
                "latency": {
                    "p50_ms": 32100,
                    "p95_ms": 34500,
                    "p99_ms": 36200,
                }
            },
        }

        comparer = BenchmarkComparer()
        table = comparer.generate_latency_table(baseline_data, test_data)

        # Verify table structure
        assert "| Metric | Baseline (Q4_K_M) | Test (Q3_K_M) | Delta |" in table
        assert "|--------|-------------------|---------------|-------|" in table

        # Verify P50 row with improvement indicator
        # (32100 - 39600) / 39600 * 100 = -18.94% rounds to -18.9%
        assert "| P50 Latency | 39.6s | 32.1s | -18.9% ↓ |" in table

        # Verify P95 row
        assert "| P95 Latency | 42.1s | 34.5s | -18.1% ↓ |" in table

        # Verify P99 row
        assert "| P99 Latency | 43.8s | 36.2s | -17.4% ↓ |" in table

    def test_generate_throughput_comparison_table(self) -> None:
        """Test generating markdown table for throughput comparison."""
        from scripts.benchmark.compare import BenchmarkComparer

        baseline_data = {
            "model_name": "Q4_K_M",
            "metrics": {
                "throughput": {
                    "requests_per_min": 1.51,
                    "tokens_per_sec": 12.4,
                }
            },
        }

        test_data = {
            "model_name": "Q3_K_M",
            "metrics": {
                "throughput": {
                    "requests_per_min": 1.87,
                    "tokens_per_sec": 15.3,
                }
            },
        }

        comparer = BenchmarkComparer()
        table = comparer.generate_throughput_table(baseline_data, test_data)

        assert "| Metric | Baseline (Q4_K_M) | Test (Q3_K_M) | Delta |" in table
        assert "| Requests/min | 1.51 | 1.87 | +23.8% ↑ |" in table
        assert "| Tokens/sec | 12.4 | 15.3 | +23.4% ↑ |" in table

    def test_generate_vram_comparison_table(self) -> None:
        """Test generating markdown table for VRAM comparison."""
        from scripts.benchmark.compare import BenchmarkComparer

        baseline_data = {
            "model_name": "Q4_K_M",
            "metrics": {
                "vram": {
                    "peak_mb": 14700,
                    "steady_state_mb": 14200,
                }
            },
        }

        test_data = {
            "model_name": "Q3_K_M",
            "metrics": {
                "vram": {
                    "peak_mb": 11200,
                    "steady_state_mb": 10800,
                }
            },
        }

        comparer = BenchmarkComparer()
        table = comparer.generate_vram_table(baseline_data, test_data)

        assert "| Metric | Baseline (Q4_K_M) | Test (Q3_K_M) | Delta |" in table
        assert "| VRAM Peak | 14.7 GB | 11.2 GB | -23.8% ↓ |" in table
        assert "| VRAM Steady-State | 14.2 GB | 10.8 GB | -23.9% ↓ |" in table

    def test_generate_quality_comparison_table(self) -> None:
        """Test generating markdown table for quality comparison."""
        from scripts.benchmark.compare import BenchmarkComparer

        baseline_data = {
            "model_name": "Q4_K_M",
            "metrics": {
                "quality": {
                    "accuracy_pct": 100.0,
                    "risk_level_match_pct": 100.0,
                }
            },
        }

        test_data = {
            "model_name": "Q3_K_M",
            "metrics": {
                "quality": {
                    "accuracy_pct": 96.2,
                    "risk_level_match_pct": 94.8,
                }
            },
        }

        comparer = BenchmarkComparer()
        table = comparer.generate_quality_table(baseline_data, test_data)

        assert "| Metric | Baseline (Q4_K_M) | Test (Q3_K_M) | Delta |" in table
        assert "| Accuracy | 100.0% | 96.2% | -3.8% ↑ |" in table
        assert "| Risk Level Match | 100.0% | 94.8% | -5.2% ↑ |" in table


class TestImprovementRegression:
    """Test highlighting improvements and regressions with symbols."""

    def test_latency_decrease_shows_improvement(self) -> None:
        """Test that latency decrease shows ↓ improvement symbol."""
        from scripts.benchmark.compare import format_delta_with_indicator

        delta = -19.0  # 19% improvement (lower is better for latency)
        indicator = format_delta_with_indicator(delta, lower_is_better=True)

        assert indicator == "-19.0% ↓"

    def test_latency_increase_shows_regression(self) -> None:
        """Test that latency increase shows ↑ regression symbol."""
        from scripts.benchmark.compare import format_delta_with_indicator

        delta = 15.5  # 15.5% regression (higher is worse for latency)
        indicator = format_delta_with_indicator(delta, lower_is_better=True)

        assert indicator == "+15.5% ↑"

    def test_throughput_increase_shows_improvement(self) -> None:
        """Test that throughput increase shows ↑ improvement symbol."""
        from scripts.benchmark.compare import format_delta_with_indicator

        delta = 23.8  # 23.8% improvement (higher is better for throughput)
        indicator = format_delta_with_indicator(delta, lower_is_better=False)

        assert indicator == "+23.8% ↑"

    def test_vram_decrease_shows_improvement(self) -> None:
        """Test that VRAM decrease shows ↓ improvement symbol."""
        from scripts.benchmark.compare import format_delta_with_indicator

        delta = -24.0  # 24% improvement (lower is better for VRAM)
        indicator = format_delta_with_indicator(delta, lower_is_better=True)

        assert indicator == "-24.0% ↓"

    def test_quality_decrease_shows_regression(self) -> None:
        """Test that quality decrease shows ↑ regression symbol."""
        from scripts.benchmark.compare import format_delta_with_indicator

        delta = -3.8  # 3.8% regression (lower is worse for quality)
        indicator = format_delta_with_indicator(delta, lower_is_better=False)

        assert indicator == "-3.8% ↑"

    def test_zero_delta_shows_no_change(self) -> None:
        """Test that zero delta shows no change indicator."""
        from scripts.benchmark.compare import format_delta_with_indicator

        delta = 0.0
        indicator = format_delta_with_indicator(delta, lower_is_better=True)

        assert indicator == "0.0% —"


class TestMissingMetrics:
    """Test handling of missing or incomplete metrics."""

    def test_missing_latency_metric_shows_na(self) -> None:
        """Test that missing latency metrics show 'N/A' in table."""
        from scripts.benchmark.compare import BenchmarkComparer

        baseline_data = {
            "model_name": "Q4_K_M",
            "metrics": {
                "latency": {
                    "p50_ms": 39600,
                    "p95_ms": 42100,
                    # p99_ms missing
                }
            },
        }

        test_data = {
            "model_name": "Q3_K_M",
            "metrics": {
                "latency": {
                    "p50_ms": 32100,
                    "p95_ms": 34500,
                    "p99_ms": 36200,
                }
            },
        }

        comparer = BenchmarkComparer()
        table = comparer.generate_latency_table(baseline_data, test_data)

        assert "| P99 Latency | N/A | 36.2s | N/A |" in table

    def test_missing_entire_metric_category(self) -> None:
        """Test that missing entire metric category is handled gracefully."""
        from scripts.benchmark.compare import BenchmarkComparer

        baseline_data = {
            "model_name": "Q4_K_M",
            "metrics": {
                "latency": {"p50_ms": 39600},
                # throughput missing
            },
        }

        test_data = {
            "model_name": "Q3_K_M",
            "metrics": {
                "latency": {"p50_ms": 32100},
                "throughput": {
                    "requests_per_min": 1.87,
                    "tokens_per_sec": 15.3,
                },
            },
        }

        comparer = BenchmarkComparer()
        table = comparer.generate_throughput_table(baseline_data, test_data)

        assert "N/A" in table  # Should show N/A for missing baseline throughput

    def test_both_metrics_missing_shows_na(self) -> None:
        """Test that missing metrics in both baseline and test show N/A."""
        from scripts.benchmark.compare import BenchmarkComparer

        baseline_data = {
            "model_name": "Q4_K_M",
            "metrics": {
                "vram": {
                    "peak_mb": 14700,
                    # steady_state_mb missing
                }
            },
        }

        test_data = {
            "model_name": "Q3_K_M",
            "metrics": {
                "vram": {
                    "peak_mb": 11200,
                    # steady_state_mb missing
                }
            },
        }

        comparer = BenchmarkComparer()
        table = comparer.generate_vram_table(baseline_data, test_data)

        assert "| VRAM Steady-State | N/A | N/A | N/A |" in table


class TestCLIInterface:
    """Test command-line interface for benchmark comparison."""

    def test_cli_requires_baseline_and_test_args(self) -> None:
        """Test that CLI requires both baseline and test file arguments."""
        from scripts.benchmark.compare import parse_args

        # Test with missing arguments
        with pytest.raises(SystemExit):
            parse_args([])  # No arguments provided

    def test_cli_parse_baseline_and_test_files(self, tmp_path: Path) -> None:
        """Test parsing baseline and test file paths from CLI."""
        from scripts.benchmark.compare import parse_args

        baseline = tmp_path / "baseline.json"
        test = tmp_path / "test.json"

        baseline.touch()
        test.touch()

        args = parse_args(
            [
                "--baseline",
                str(baseline),
                "--test",
                str(test),
            ]
        )

        assert args.baseline == baseline
        assert args.test == test

    def test_cli_parse_output_file(self, tmp_path: Path) -> None:
        """Test parsing optional output file path from CLI."""
        from scripts.benchmark.compare import parse_args

        baseline = tmp_path / "baseline.json"
        test = tmp_path / "test.json"
        output = tmp_path / "comparison.md"

        baseline.touch()
        test.touch()

        args = parse_args(
            [
                "--baseline",
                str(baseline),
                "--test",
                str(test),
                "--output",
                str(output),
            ]
        )

        assert args.output == output

    def test_cli_default_output_to_stdout(self, tmp_path: Path) -> None:
        """Test that CLI defaults to stdout if no output file specified."""
        from scripts.benchmark.compare import parse_args

        baseline = tmp_path / "baseline.json"
        test = tmp_path / "test.json"

        baseline.touch()
        test.touch()

        args = parse_args(
            [
                "--baseline",
                str(baseline),
                "--test",
                str(test),
            ]
        )

        assert args.output is None  # None means stdout


class TestFullComparisonReport:
    """Test generating complete comparison report with all sections."""

    def test_generate_full_comparison_report(self, tmp_path: Path) -> None:
        """Test generating a complete comparison report."""
        from scripts.benchmark.compare import BenchmarkComparer

        baseline_data = {
            "model_name": "nemotron-70b-Q4_K_M",
            "timestamp": "2026-02-05T10:30:00",
            "metrics": {
                "latency": {
                    "p50_ms": 39600,
                    "p95_ms": 42100,
                    "p99_ms": 43800,
                },
                "throughput": {
                    "requests_per_min": 1.51,
                    "tokens_per_sec": 12.4,
                },
                "vram": {
                    "peak_mb": 14700,
                    "steady_state_mb": 14200,
                },
                "quality": {
                    "accuracy_pct": 100.0,
                    "risk_level_match_pct": 100.0,
                },
            },
        }

        test_data = {
            "model_name": "nemotron-70b-Q3_K_M",
            "timestamp": "2026-02-05T11:00:00",
            "metrics": {
                "latency": {
                    "p50_ms": 32100,
                    "p95_ms": 34500,
                    "p99_ms": 36200,
                },
                "throughput": {
                    "requests_per_min": 1.87,
                    "tokens_per_sec": 15.3,
                },
                "vram": {
                    "peak_mb": 11200,
                    "steady_state_mb": 10800,
                },
                "quality": {
                    "accuracy_pct": 96.2,
                    "risk_level_match_pct": 94.8,
                },
            },
        }

        baseline_file = tmp_path / "baseline.json"
        test_file = tmp_path / "test.json"

        baseline_file.write_text(json.dumps(baseline_data, indent=2))
        test_file.write_text(json.dumps(test_data, indent=2))

        comparer = BenchmarkComparer()
        report = comparer.generate_comparison_report(baseline_file, test_file)

        # Verify report structure
        assert "# Benchmark Comparison Report" in report
        assert "## Latency Comparison" in report
        assert "## Throughput Comparison" in report
        assert "## VRAM Comparison" in report
        assert "## Quality Comparison" in report

        # Verify report contains data from all sections
        assert "39.6s" in report  # Baseline latency
        assert "32.1s" in report  # Test latency
        assert "14.7 GB" in report  # Baseline VRAM
        assert "11.2 GB" in report  # Test VRAM
        assert "100.0%" in report  # Baseline quality
        assert "96.2%" in report  # Test quality

    def test_save_report_to_file(self, tmp_path: Path) -> None:
        """Test saving comparison report to a file."""
        from scripts.benchmark.compare import BenchmarkComparer

        baseline_data = {
            "model_name": "Q4_K_M",
            "metrics": {
                "latency": {"p50_ms": 39600},
            },
        }

        test_data = {
            "model_name": "Q3_K_M",
            "metrics": {
                "latency": {"p50_ms": 32100},
            },
        }

        baseline_file = tmp_path / "baseline.json"
        test_file = tmp_path / "test.json"
        output_file = tmp_path / "comparison.md"

        baseline_file.write_text(json.dumps(baseline_data))
        test_file.write_text(json.dumps(test_data))

        comparer = BenchmarkComparer()
        comparer.compare_and_save(baseline_file, test_file, output_file)

        assert output_file.exists()
        content = output_file.read_text()
        assert "# Benchmark Comparison Report" in content
        assert "Q4_K_M" in content
        assert "Q3_K_M" in content


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_identical_results_show_zero_deltas(self) -> None:
        """Test that identical baseline and test results show 0% deltas."""
        from scripts.benchmark.compare import BenchmarkComparer

        data = {
            "model_name": "same-model",
            "metrics": {
                "latency": {"p50_ms": 39600},
                "vram": {"peak_mb": 14700},
            },
        }

        comparer = BenchmarkComparer()
        table = comparer.generate_latency_table(data, data)

        assert "0.0% —" in table  # Zero delta with no-change indicator

    def test_very_large_deltas_formatted_correctly(self) -> None:
        """Test that very large percentage deltas are formatted correctly."""
        from scripts.benchmark.compare import calculate_percentage_delta

        baseline = 1000
        test = 5000

        delta = calculate_percentage_delta(baseline, test)

        assert delta == pytest.approx(400.0, abs=0.01)  # 400% increase

    def test_very_small_deltas_show_precision(self) -> None:
        """Test that very small percentage deltas show appropriate precision."""
        from scripts.benchmark.compare import format_delta_with_indicator

        delta = 0.05  # 0.05% change
        indicator = format_delta_with_indicator(delta, lower_is_better=True)

        assert "0.0%" in indicator or "0.1%" in indicator  # Should round appropriately

    def test_empty_metrics_handled_gracefully(self, tmp_path: Path) -> None:
        """Test that empty metrics dictionary is handled gracefully."""
        from scripts.benchmark.compare import BenchmarkComparer

        baseline_data = {
            "model_name": "test",
            "metrics": {},
        }

        test_data = {
            "model_name": "test2",
            "metrics": {},
        }

        baseline_file = tmp_path / "baseline.json"
        test_file = tmp_path / "test.json"

        baseline_file.write_text(json.dumps(baseline_data))
        test_file.write_text(json.dumps(test_data))

        comparer = BenchmarkComparer()
        report = comparer.generate_comparison_report(baseline_file, test_file)

        # Should generate a report even with empty metrics
        assert "# Benchmark Comparison Report" in report
        assert "N/A" in report  # Missing metrics should show N/A


class TestMultipleComparisons:
    """Test comparing multiple benchmark runs."""

    def test_compare_three_benchmark_runs(self, tmp_path: Path) -> None:
        """Test comparing three different benchmark runs."""
        from scripts.benchmark.compare import BenchmarkComparer

        q4_data = {
            "model_name": "Q4_K_M",
            "metrics": {"latency": {"p50_ms": 39600}},
        }

        q3_data = {
            "model_name": "Q3_K_M",
            "metrics": {"latency": {"p50_ms": 32100}},
        }

        q2_data = {
            "model_name": "Q2_K",
            "metrics": {"latency": {"p50_ms": 28500}},
        }

        q4_file = tmp_path / "q4.json"
        q3_file = tmp_path / "q3.json"
        q2_file = tmp_path / "q2.json"

        q4_file.write_text(json.dumps(q4_data))
        q3_file.write_text(json.dumps(q3_data))
        q2_file.write_text(json.dumps(q2_data))

        comparer = BenchmarkComparer()
        report = comparer.compare_multiple([q4_file, q3_file, q2_file])

        # Should show all three models in comparison
        assert "Q4_K_M" in report
        assert "Q3_K_M" in report
        assert "Q2_K" in report

        # Should show comparative deltas
        assert "39.6s" in report
        assert "32.1s" in report
        assert "28.5s" in report
