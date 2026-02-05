#!/usr/bin/env python3
"""Benchmark comparison tool for comparing LLM performance metrics.

This tool loads benchmark result JSON files, calculates deltas between runs,
and generates markdown comparison tables showing:
- Latency comparison (P50, P95, P99)
- Throughput comparison (req/min, tokens/sec)
- VRAM comparison (peak, steady-state)
- Quality comparison (accuracy %, risk level match %)

Highlights improvements/regressions with symbols (up/down arrows).

Usage:
    # Compare two benchmark runs
    python scripts/benchmark/compare.py --baseline results/q4_k_m.json --test results/q3_k_m.json

    # Save comparison to file
    python scripts/benchmark/compare.py --baseline baseline.json --test test.json --output comparison.md

    # Compare multiple runs
    python scripts/benchmark/compare.py --multiple q4.json q3.json q2.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


class BenchmarkComparer:
    """Compare benchmark results and generate comparison reports."""

    def load_benchmark_result(self, file_path: Path) -> dict[str, Any]:
        """Load a benchmark result JSON file.

        Args:
            file_path: Path to the benchmark result JSON file

        Returns:
            Parsed benchmark result data

        Raises:
            FileNotFoundError: If the file does not exist
            ValueError: If JSON is invalid or missing required fields
        """
        if not file_path.exists():
            raise FileNotFoundError("Benchmark result file not found")

        try:
            content = file_path.read_text()
            data: dict[str, Any] = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}") from e

        # Validate required fields
        required_fields = ["model_name", "metrics"]
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")

        return data

    def calculate_metric_deltas(
        self,
        baseline: dict[str, Any],
        test: dict[str, Any],
        metric_category: str,
    ) -> dict[str, float]:
        """Calculate percentage deltas for a metric category.

        Args:
            baseline: Baseline benchmark data
            test: Test benchmark data
            metric_category: Metric category (e.g., 'latency', 'throughput')

        Returns:
            Dictionary mapping metric names to percentage deltas
        """
        baseline_metrics = baseline.get(metric_category, {})
        test_metrics = test.get(metric_category, {})

        deltas = {}
        all_keys = set(baseline_metrics.keys()) | set(test_metrics.keys())

        for key in all_keys:
            baseline_val = baseline_metrics.get(key)
            test_val = test_metrics.get(key)

            if baseline_val is not None and test_val is not None:
                deltas[key] = calculate_percentage_delta(baseline_val, test_val)

        return deltas

    def generate_latency_table(
        self,
        baseline: dict[str, Any],
        test: dict[str, Any],
    ) -> str:
        """Generate markdown table for latency comparison.

        Args:
            baseline: Baseline benchmark data
            test: Test benchmark data

        Returns:
            Markdown table string
        """
        baseline_name = baseline.get("model_name", "Baseline")
        test_name = test.get("model_name", "Test")

        baseline_latency = baseline.get("metrics", {}).get("latency", {})
        test_latency = test.get("metrics", {}).get("latency", {})

        lines = [
            f"| Metric | Baseline ({baseline_name}) | Test ({test_name}) | Delta |",
            "|--------|-------------------|---------------|-------|",
        ]

        metrics = [
            ("P50 Latency", "p50_ms"),
            ("P95 Latency", "p95_ms"),
            ("P99 Latency", "p99_ms"),
        ]

        for label, key in metrics:
            baseline_val = baseline_latency.get(key)
            test_val = test_latency.get(key)

            baseline_str = self._format_latency(baseline_val)
            test_str = self._format_latency(test_val)

            if baseline_val is not None and test_val is not None:
                delta = calculate_percentage_delta(baseline_val, test_val)
                delta_str = format_delta_with_indicator(delta, lower_is_better=True)
            else:
                delta_str = "N/A"

            lines.append(f"| {label} | {baseline_str} | {test_str} | {delta_str} |")

        return "\n".join(lines)

    def _format_latency(self, value_ms: float | None) -> str:
        """Format latency value in milliseconds to seconds string."""
        if value_ms is None:
            return "N/A"
        seconds = value_ms / 1000
        return f"{seconds:.1f}s"

    def generate_throughput_table(
        self,
        baseline: dict[str, Any],
        test: dict[str, Any],
    ) -> str:
        """Generate markdown table for throughput comparison.

        Args:
            baseline: Baseline benchmark data
            test: Test benchmark data

        Returns:
            Markdown table string
        """
        baseline_name = baseline.get("model_name", "Baseline")
        test_name = test.get("model_name", "Test")

        baseline_throughput = baseline.get("metrics", {}).get("throughput", {})
        test_throughput = test.get("metrics", {}).get("throughput", {})

        lines = [
            f"| Metric | Baseline ({baseline_name}) | Test ({test_name}) | Delta |",
            "|--------|-------------------|---------------|-------|",
        ]

        metrics = [
            ("Requests/min", "requests_per_min"),
            ("Tokens/sec", "tokens_per_sec"),
        ]

        for label, key in metrics:
            baseline_val = baseline_throughput.get(key)
            test_val = test_throughput.get(key)

            baseline_str = self._format_throughput(baseline_val)
            test_str = self._format_throughput(test_val)

            if baseline_val is not None and test_val is not None:
                delta = calculate_percentage_delta(baseline_val, test_val)
                delta_str = format_delta_with_indicator(delta, lower_is_better=False)
            else:
                delta_str = "N/A"

            lines.append(f"| {label} | {baseline_str} | {test_str} | {delta_str} |")

        return "\n".join(lines)

    def _format_throughput(self, value: float | None) -> str:
        """Format throughput value."""
        if value is None:
            return "N/A"
        # Check if the value needs decimal places
        if value == int(value):
            return str(int(value))
        return f"{value:.2f}" if value < 10 else f"{value:.1f}"

    def generate_vram_table(
        self,
        baseline: dict[str, Any],
        test: dict[str, Any],
    ) -> str:
        """Generate markdown table for VRAM comparison.

        Args:
            baseline: Baseline benchmark data
            test: Test benchmark data

        Returns:
            Markdown table string
        """
        baseline_name = baseline.get("model_name", "Baseline")
        test_name = test.get("model_name", "Test")

        baseline_vram = baseline.get("metrics", {}).get("vram", {})
        test_vram = test.get("metrics", {}).get("vram", {})

        lines = [
            f"| Metric | Baseline ({baseline_name}) | Test ({test_name}) | Delta |",
            "|--------|-------------------|---------------|-------|",
        ]

        metrics = [
            ("VRAM Peak", "peak_mb"),
            ("VRAM Steady-State", "steady_state_mb"),
        ]

        for label, key in metrics:
            baseline_val = baseline_vram.get(key)
            test_val = test_vram.get(key)

            baseline_str = self._format_vram(baseline_val)
            test_str = self._format_vram(test_val)

            if baseline_val is not None and test_val is not None:
                delta = calculate_percentage_delta(baseline_val, test_val)
                delta_str = format_delta_with_indicator(delta, lower_is_better=True)
            else:
                delta_str = "N/A"

            lines.append(f"| {label} | {baseline_str} | {test_str} | {delta_str} |")

        return "\n".join(lines)

    def _format_vram(self, value_mb: float | None) -> str:
        """Format VRAM value from MB to GB string."""
        if value_mb is None:
            return "N/A"
        gb = value_mb / 1000
        return f"{gb:.1f} GB"

    def generate_quality_table(
        self,
        baseline: dict[str, Any],
        test: dict[str, Any],
    ) -> str:
        """Generate markdown table for quality comparison.

        Args:
            baseline: Baseline benchmark data
            test: Test benchmark data

        Returns:
            Markdown table string
        """
        baseline_name = baseline.get("model_name", "Baseline")
        test_name = test.get("model_name", "Test")

        baseline_quality = baseline.get("metrics", {}).get("quality", {})
        test_quality = test.get("metrics", {}).get("quality", {})

        lines = [
            f"| Metric | Baseline ({baseline_name}) | Test ({test_name}) | Delta |",
            "|--------|-------------------|---------------|-------|",
        ]

        metrics = [
            ("Accuracy", "accuracy_pct"),
            ("Risk Level Match", "risk_level_match_pct"),
        ]

        for label, key in metrics:
            baseline_val = baseline_quality.get(key)
            test_val = test_quality.get(key)

            baseline_str = self._format_percentage(baseline_val)
            test_str = self._format_percentage(test_val)

            if baseline_val is not None and test_val is not None:
                delta = calculate_percentage_delta(baseline_val, test_val)
                delta_str = format_delta_with_indicator(delta, lower_is_better=False)
            else:
                delta_str = "N/A"

            lines.append(f"| {label} | {baseline_str} | {test_str} | {delta_str} |")

        return "\n".join(lines)

    def _format_percentage(self, value: float | None) -> str:
        """Format percentage value."""
        if value is None:
            return "N/A"
        return f"{value:.1f}%"

    def generate_comparison_report(
        self,
        baseline_file: Path,
        test_file: Path,
    ) -> str:
        """Generate complete comparison report.

        Args:
            baseline_file: Path to baseline benchmark result
            test_file: Path to test benchmark result

        Returns:
            Complete markdown comparison report
        """
        baseline = self.load_benchmark_result(baseline_file)
        test = self.load_benchmark_result(test_file)

        sections = [
            "# Benchmark Comparison Report",
            "",
            "## Latency Comparison",
            "",
            self.generate_latency_table(baseline, test),
            "",
            "## Throughput Comparison",
            "",
            self.generate_throughput_table(baseline, test),
            "",
            "## VRAM Comparison",
            "",
            self.generate_vram_table(baseline, test),
            "",
            "## Quality Comparison",
            "",
            self.generate_quality_table(baseline, test),
        ]

        return "\n".join(sections)

    def compare_and_save(
        self,
        baseline_file: Path,
        test_file: Path,
        output_file: Path,
    ) -> None:
        """Compare benchmarks and save report to file.

        Args:
            baseline_file: Path to baseline benchmark result
            test_file: Path to test benchmark result
            output_file: Path to save comparison report
        """
        report = self.generate_comparison_report(baseline_file, test_file)
        output_file.write_text(report)

    def compare_multiple(self, benchmark_files: list[Path]) -> str:
        """Compare multiple benchmark runs.

        Args:
            benchmark_files: List of benchmark result file paths

        Returns:
            Markdown comparison report for all runs
        """
        if len(benchmark_files) < 2:
            raise ValueError("Need at least 2 benchmark files to compare")

        # Load all benchmark results
        results = [self.load_benchmark_result(f) for f in benchmark_files]

        # Build header with all model names
        model_names = [r.get("model_name", f"Model {i}") for i, r in enumerate(results)]
        header = "| Metric | " + " | ".join(model_names) + " |"
        separator = "|--------|" + "|".join(["--------"] * len(model_names)) + "|"

        sections = [
            "# Benchmark Comparison Report",
            "",
            "## Latency Comparison",
            "",
            header,
            separator,
        ]

        # Generate latency rows
        metrics = [
            ("P50 Latency", "latency", "p50_ms"),
            ("P95 Latency", "latency", "p95_ms"),
            ("P99 Latency", "latency", "p99_ms"),
        ]

        for label, category, key in metrics:
            values = []
            for result in results:
                val = result.get("metrics", {}).get(category, {}).get(key)
                if val is not None:
                    values.append(self._format_latency(val))
                else:
                    values.append("N/A")
            sections.append(f"| {label} | " + " | ".join(values) + " |")

        # Throughput section
        sections.extend(
            [
                "",
                "## Throughput Comparison",
                "",
                header,
                separator,
            ]
        )

        throughput_metrics = [
            ("Requests/min", "throughput", "requests_per_min"),
            ("Tokens/sec", "throughput", "tokens_per_sec"),
        ]

        for label, category, key in throughput_metrics:
            values = []
            for result in results:
                val = result.get("metrics", {}).get(category, {}).get(key)
                if val is not None:
                    values.append(self._format_throughput(val))
                else:
                    values.append("N/A")
            sections.append(f"| {label} | " + " | ".join(values) + " |")

        # VRAM section
        sections.extend(
            [
                "",
                "## VRAM Comparison",
                "",
                header,
                separator,
            ]
        )

        vram_metrics = [
            ("VRAM Peak", "vram", "peak_mb"),
            ("VRAM Steady-State", "vram", "steady_state_mb"),
        ]

        for label, category, key in vram_metrics:
            values = []
            for result in results:
                val = result.get("metrics", {}).get(category, {}).get(key)
                if val is not None:
                    values.append(self._format_vram(val))
                else:
                    values.append("N/A")
            sections.append(f"| {label} | " + " | ".join(values) + " |")

        # Quality section
        sections.extend(
            [
                "",
                "## Quality Comparison",
                "",
                header,
                separator,
            ]
        )

        quality_metrics = [
            ("Accuracy", "quality", "accuracy_pct"),
            ("Risk Level Match", "quality", "risk_level_match_pct"),
        ]

        for label, category, key in quality_metrics:
            values = []
            for result in results:
                val = result.get("metrics", {}).get(category, {}).get(key)
                if val is not None:
                    values.append(self._format_percentage(val))
                else:
                    values.append("N/A")
            sections.append(f"| {label} | " + " | ".join(values) + " |")

        return "\n".join(sections)


def calculate_percentage_delta(baseline: float, test: float) -> float:
    """Calculate percentage change from baseline to test.

    Args:
        baseline: Baseline value
        test: Test value

    Returns:
        Percentage change (positive for increase, negative for decrease)

    Raises:
        ValueError: If baseline is zero
    """
    if baseline == 0:
        raise ValueError("Baseline value cannot be zero")

    # Use absolute value of baseline for percentage calculation
    # This ensures consistent behavior with negative values
    return ((test - baseline) / abs(baseline)) * 100


def format_delta_with_indicator(delta: float, lower_is_better: bool) -> str:
    """Format delta percentage with improvement/regression indicator.

    Args:
        delta: Percentage delta
        lower_is_better: Whether lower values are better (True for latency/VRAM)

    Returns:
        Formatted string with delta and symbol (up/down arrow or dash)
    """
    if delta == 0:
        return "0.0% \u2014"

    # Round to 1 decimal place using half-away-from-zero rounding
    from decimal import ROUND_HALF_UP, Decimal

    rounded_delta = float(Decimal(str(delta)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))

    # Format the percentage with sign
    sign = "+" if rounded_delta > 0 else ""
    formatted = f"{sign}{rounded_delta:.1f}%"

    # Determine the indicator symbol based on the original delta sign
    if lower_is_better:
        # For latency/VRAM: negative delta = improvement (down arrow),
        # positive = regression (up arrow)
        symbol = "\u2193" if delta < 0 else "\u2191"
    else:
        # For throughput/quality: positive delta = improvement (up arrow),
        # negative = regression (still up arrow to indicate it's bad)
        symbol = "\u2191"

    return f"{formatted} {symbol}"


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        args: Command-line arguments (None for sys.argv)

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="Compare benchmark results and generate comparison reports."
    )

    parser.add_argument(
        "--baseline",
        type=Path,
        required=True,
        help="Path to baseline benchmark result JSON file",
    )

    parser.add_argument(
        "--test",
        type=Path,
        required=True,
        help="Path to test benchmark result JSON file",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output file for comparison report (default: stdout)",
    )

    return parser.parse_args(args)


def main() -> None:
    """Main entry point for CLI."""
    args = parse_args()

    comparer = BenchmarkComparer()

    if args.output:
        comparer.compare_and_save(args.baseline, args.test, args.output)
        print(f"Comparison report saved to: {args.output}")
    else:
        report = comparer.generate_comparison_report(args.baseline, args.test)
        print(report)


if __name__ == "__main__":
    main()
