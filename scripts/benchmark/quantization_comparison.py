#!/usr/bin/env python3
"""Quantization comparison benchmarking for LLM inference optimization.

This module benchmarks different quantization formats (Q4_K_M, Q4_K_S, Q3_K_M,
Q3_K_S, Q2_K_L) to find the optimal VRAM/quality tradeoff for Nemotron-3-Nano.

Usage:
    python scripts/benchmark/quantization_comparison.py \
        --formats Q4_K_M Q3_K_M Q2_K_L \
        --baseline Q4_K_M \
        --output docs/reports/quantization-comparison.md
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import time
from pathlib import Path
from typing import Any

import httpx
import numpy as np

# Supported quantization formats for Nemotron-3-Nano-30B-A3B
QUANTIZATION_FORMATS = ["Q4_K_M", "Q4_K_S", "Q3_K_M", "Q3_K_S", "Q2_K_L"]

# Default baseline format (highest quality)
BASELINE_FORMAT = "Q4_K_M"

# Default model base path
DEFAULT_MODEL_BASE_PATH = Path("/models/nemotron")

# Common English words for gibberish detection
COMMON_WORDS = {
    "the",
    "a",
    "an",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "have",
    "has",
    "had",
    "do",
    "does",
    "did",
    "will",
    "would",
    "could",
    "should",
    "may",
    "might",
    "must",
    "shall",
    "can",
    "need",
    "dare",
    "ought",
    "used",
    "to",
    "of",
    "in",
    "for",
    "on",
    "with",
    "at",
    "by",
    "from",
    "as",
    "into",
    "through",
    "during",
    "before",
    "after",
    "above",
    "below",
    "between",
    "under",
    "again",
    "further",
    "then",
    "once",
    "and",
    "but",
    "or",
    "nor",
    "so",
    "yet",
    "both",
    "either",
    "neither",
    "not",
    "only",
    "own",
    "same",
    "than",
    "too",
    "very",
    "just",
    "also",
    "now",
    "here",
    "there",
    "when",
    "where",
    "why",
    "how",
    "all",
    "each",
    "every",
    "few",
    "more",
    "most",
    "other",
    "some",
    "such",
    "no",
    "any",
    "security",
    "camera",
    "detected",
    "motion",
    "person",
    "vehicle",
    "door",
    "window",
    "risk",
    "alert",
    "low",
    "medium",
    "high",
    "critical",
}


def get_model_path(quantization_format: str) -> Path:
    """Get the model file path for a quantization format.

    Args:
        quantization_format: The quantization format (e.g., "Q4_K_M")

    Returns:
        Path to the model file

    Raises:
        ValueError: If the format is unknown
    """
    if quantization_format not in QUANTIZATION_FORMATS:
        raise ValueError(f"Unknown quantization format: {quantization_format}")

    return DEFAULT_MODEL_BASE_PATH / f"nemotron-nano-{quantization_format.lower()}.gguf"


async def run_nvidia_smi() -> float:
    """Run nvidia-smi and return VRAM usage in MB.

    Returns:
        VRAM usage in megabytes

    Raises:
        RuntimeError: If nvidia-smi fails
    """
    process = await asyncio.create_subprocess_exec(
        "nvidia-smi",
        "--query-gpu=memory.used",
        "--format=csv,noheader,nounits",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        raise RuntimeError(f"nvidia-smi failed: {stderr.decode().strip()}")

    # Parse first GPU's VRAM usage
    output = stdout.decode().strip()
    first_line = output.split("\n")[0].strip()
    return float(first_line.replace("MiB", "").strip())


async def capture_vram_metrics(
    duration_sec: float = 1.0, interval_sec: float = 0.1
) -> dict[str, float]:
    """Capture VRAM metrics over a duration.

    Args:
        duration_sec: How long to monitor
        interval_sec: Polling interval

    Returns:
        Dictionary with peak_mb and steady_state_mb
    """
    samples: list[float] = []
    start_time = time.perf_counter()

    while (time.perf_counter() - start_time) < duration_sec:
        try:
            vram = await run_nvidia_smi()
            samples.append(vram)
        except RuntimeError:
            pass
        await asyncio.sleep(interval_sec)

    if not samples:
        return {"peak_mb": 0.0, "steady_state_mb": 0.0}

    return {
        "peak_mb": float(np.max(samples)),
        "steady_state_mb": float(np.median(samples)),
    }


def calculate_quality_delta(baseline: float, test: float) -> float:
    """Calculate quality delta as percentage points.

    Args:
        baseline: Baseline quality score (0-1)
        test: Test quality score (0-1)

    Returns:
        Delta in percentage points (e.g., -5.0 means 5 percentage points worse)

    Raises:
        ValueError: If baseline is zero
    """
    if baseline == 0:
        raise ValueError("Baseline quality cannot be zero")

    # Convert to percentage points
    return (test - baseline) * 100


def calculate_vram_savings(baseline_mb: float, test_mb: float) -> float:
    """Calculate VRAM savings percentage.

    Args:
        baseline_mb: Baseline VRAM usage in MB
        test_mb: Test VRAM usage in MB

    Returns:
        Savings percentage (positive = less VRAM used)
    """
    if baseline_mb == 0:
        return 0.0

    return ((baseline_mb - test_mb) / baseline_mb) * 100


def detect_gibberish_output(text: str) -> bool:
    """Detect if output is gibberish (from over-quantized model).

    Args:
        text: The text to check

    Returns:
        True if the text appears to be gibberish
    """
    if not text or len(text.strip()) < 10:
        return True

    # Tokenize into words
    words = re.findall(r"\b[a-zA-Z]+\b", text.lower())

    if len(words) < 3:
        return True

    # Check what percentage of words are common English words
    common_count = sum(1 for word in words if word in COMMON_WORDS)
    ratio = common_count / len(words)

    # If less than 20% of words are common, likely gibberish
    return ratio < 0.2


def is_quality_acceptable(test: float, baseline: float, threshold: float = 0.95) -> bool:
    """Check if test quality is acceptable relative to baseline.

    Args:
        test: Test quality score (0-1)
        baseline: Baseline quality score (0-1)
        threshold: Minimum acceptable ratio (default 0.95 = 95% of baseline)

    Returns:
        True if quality is acceptable
    """
    if baseline == 0:
        return False

    return (test / baseline) >= threshold


def generate_comparison_results(
    benchmark_results: list[dict[str, Any]], baseline: str
) -> dict[str, Any]:
    """Generate comparison results from benchmark data.

    Args:
        benchmark_results: List of benchmark results per format
        baseline: Baseline format name

    Returns:
        Comparison results dictionary
    """
    # Find baseline result
    baseline_result = next((r for r in benchmark_results if r["format"] == baseline), None)

    if baseline_result is None:
        baseline_vram = None
        baseline_quality = None
    else:
        baseline_vram = baseline_result["vram"]["peak_mb"] if baseline_result.get("vram") else None
        baseline_quality = baseline_result.get("quality_score")

    formats = []
    for result in benchmark_results:
        fmt = result["format"]
        vram = result.get("vram")
        quality = result.get("quality_score")

        # Calculate relative metrics
        if vram is None or baseline_vram is None:
            vram_savings = None
        elif fmt == baseline:
            vram_savings = 0.0
        else:
            vram_savings = calculate_vram_savings(baseline_vram, vram["peak_mb"])

        if quality is None or baseline_quality is None:
            quality_delta = None
        elif fmt == baseline:
            quality_delta = 0.0
        else:
            quality_delta = calculate_quality_delta(baseline_quality, quality)

        format_result = {
            "format": fmt,
            "vram_peak_mb": vram["peak_mb"] if vram else None,
            "quality_score": quality,
            "vram_savings_pct": vram_savings,
            "quality_delta_pct": quality_delta,
        }

        # Check if quality is acceptable
        if quality is not None and baseline_quality is not None:
            format_result["acceptable"] = is_quality_acceptable(quality, baseline_quality)

        formats.append(format_result)

    return {
        "baseline": baseline,
        "formats": formats,
    }


def get_tradeoff_curve_data(comparison: dict[str, Any]) -> dict[str, Any]:
    """Extract tradeoff curve data from comparison results.

    Args:
        comparison: Comparison results dictionary

    Returns:
        Tradeoff curve data with vram_savings, quality_loss, and formats
    """
    vram_savings = []
    quality_loss = []
    formats = []

    for fmt in comparison["formats"]:
        formats.append(fmt["format"])
        vram_savings.append(fmt.get("vram_savings_pct", 0) or 0)
        quality_loss.append(abs(fmt.get("quality_delta_pct", 0) or 0))

    return {
        "vram_savings": vram_savings,
        "quality_loss": quality_loss,
        "formats": formats,
    }


def select_recommended_format(
    comparison: dict[str, Any],
    quality_threshold: float = 0.95,
    vram_target_mb: float | None = None,
) -> dict[str, Any] | None:
    """Select the recommended quantization format.

    Selects the format with best VRAM savings that still meets quality threshold.

    Args:
        comparison: Comparison results dictionary
        quality_threshold: Minimum quality ratio vs baseline
        vram_target_mb: Optional VRAM target to fit within

    Returns:
        Recommended format result, or None if none acceptable
    """
    baseline_quality = None
    for fmt in comparison["formats"]:
        if fmt["format"] == comparison["baseline"]:
            baseline_quality = fmt.get("quality_score")
            break

    if baseline_quality is None:
        return None

    # Filter acceptable formats
    acceptable: list[dict[str, Any]] = []
    for fmt in comparison["formats"]:
        quality = fmt.get("quality_score")
        if quality is None:
            continue

        if not is_quality_acceptable(quality, baseline_quality, quality_threshold):
            continue

        # Check VRAM target if specified
        if vram_target_mb is not None:
            vram = fmt.get("vram_peak_mb")
            if vram is not None and vram > vram_target_mb:
                continue

        acceptable.append(fmt)

    if not acceptable:
        return None

    # Sort by VRAM savings (descending) and return best
    acceptable.sort(key=lambda x: x.get("vram_savings_pct", 0) or 0, reverse=True)
    return acceptable[0]


def generate_markdown_report(comparison: dict[str, Any]) -> str:
    """Generate markdown comparison report.

    Args:
        comparison: Comparison results dictionary

    Returns:
        Markdown report string
    """
    lines = [
        "# Quantization Comparison Report",
        "",
        f"**Baseline:** {comparison['baseline']}",
        "",
    ]

    # Add recommendation if present
    if "recommended" in comparison:
        lines.extend(
            [
                f"**Recommended:** {comparison['recommended']}",
                "",
            ]
        )

    # Add comparison table
    lines.extend(
        [
            "## Results",
            "",
            "| Format | VRAM (GB) | Quality | VRAM Savings | Quality Delta |",
            "|--------|-----------|---------|--------------|---------------|",
        ]
    )

    for fmt in comparison["formats"]:
        vram_gb = f"{fmt['vram_peak_mb'] / 1000:.1f}" if fmt.get("vram_peak_mb") else "N/A"
        quality = f"{fmt['quality_score']:.1%}" if fmt.get("quality_score") else "N/A"
        vram_savings = (
            f"{fmt['vram_savings_pct']:.1f}%" if fmt.get("vram_savings_pct") is not None else "N/A"
        )
        quality_delta = (
            f"{fmt['quality_delta_pct']:+.1f}%"
            if fmt.get("quality_delta_pct") is not None
            else "N/A"
        )

        lines.append(
            f"| {fmt['format']} | {vram_gb} | {quality} | {vram_savings} | {quality_delta} |"
        )

    return "\n".join(lines)


def save_comparison_report(comparison: dict[str, Any], output_file: Path) -> None:
    """Save comparison report to file.

    Args:
        comparison: Comparison results dictionary
        output_file: Output file path
    """
    report = generate_markdown_report(comparison)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(report)


class QuantizationBenchmarker:
    """Benchmarks different quantization formats for LLM inference."""

    def __init__(
        self,
        service_url: str,
        model_base_path: Path | None = None,
        evaluation_set_path: Path | None = None,
    ) -> None:
        """Initialize the benchmarker.

        Args:
            service_url: URL of the LLM inference service
            model_base_path: Base path for model files
            evaluation_set_path: Path to evaluation set for quality measurement
        """
        self.service_url = service_url
        self.model_base_path = model_base_path or DEFAULT_MODEL_BASE_PATH
        self.evaluation_set_path = evaluation_set_path
        self._evaluation_set: list[dict[str, Any]] | None = None

    async def measure_vram_for_format(self, quantization_format: str) -> dict[str, float]:
        """Measure VRAM usage for a specific quantization format.

        Args:
            quantization_format: The quantization format to measure

        Returns:
            Dictionary with peak_mb and steady_state_mb
        """
        await self._load_model(quantization_format)
        return await self._capture_vram()

    async def benchmark_format(self, quantization_format: str) -> dict[str, Any]:
        """Benchmark a single quantization format.

        Args:
            quantization_format: The format to benchmark

        Returns:
            Benchmark results dictionary
        """
        # Load model
        await self._load_model(quantization_format)

        # Capture VRAM
        vram = await self._capture_vram()

        # Run inference benchmark
        inference_results = await self._run_inference_benchmark(
            quantization_format, num_requests=10
        )

        # Measure quality
        quality = await self._measure_quality(quantization_format)

        return {
            "format": quantization_format,
            "vram": vram,
            "latency_p50_ms": inference_results.get("latency_p50_ms"),
            "latency_p95_ms": inference_results.get("latency_p95_ms"),
            "tokens_per_sec": inference_results.get("tokens_per_sec"),
            "quality_score": quality,
        }

    async def benchmark_all_formats(self) -> list[dict[str, Any]]:
        """Benchmark all quantization formats.

        Returns:
            List of benchmark results for each format
        """
        results = []
        for fmt in QUANTIZATION_FORMATS:
            result = await self.benchmark_format(fmt)
            results.append(result)
        return results

    async def _load_model(self, quantization_format: str) -> None:
        """Load a model with specific quantization format.

        Args:
            quantization_format: The format to load
        """
        model_path = get_model_path(quantization_format)

        # Send request to service to load model
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.service_url}/load",
                json={"model_path": str(model_path)},
                timeout=300.0,
            )
            response.raise_for_status()

    async def _capture_vram(self) -> dict[str, float]:
        """Capture current VRAM metrics.

        Returns:
            Dictionary with peak_mb and steady_state_mb
        """
        return await capture_vram_metrics(duration_sec=2.0)

    async def _run_inference_benchmark(
        self, _quantization_format: str, num_requests: int = 10
    ) -> dict[str, Any]:
        """Run inference benchmark for a format.

        Args:
            _quantization_format: The format being benchmarked (unused)
            num_requests: Number of requests to run

        Returns:
            Inference benchmark results
        """
        latencies: list[float] = []
        total_tokens = 0

        for _ in range(num_requests):
            result = await self._send_inference_request(
                "Analyze security event: Person at front door"
            )
            latencies.append(result.get("total_time_ms", 0))
            total_tokens += result.get("tokens", 0)

        if not latencies:
            return {
                "latency_p50_ms": 0.0,
                "latency_p95_ms": 0.0,
                "tokens_per_sec": 0.0,
            }

        latencies_array = np.array(latencies)
        total_time_sec = sum(latencies) / 1000

        return {
            "latency_p50_ms": float(np.percentile(latencies_array, 50)),
            "latency_p95_ms": float(np.percentile(latencies_array, 95)),
            "tokens_per_sec": total_tokens / total_time_sec if total_time_sec > 0 else 0,
        }

    async def _send_inference_request(self, prompt: str) -> dict[str, Any]:
        """Send a single inference request.

        Args:
            prompt: The prompt to send

        Returns:
            Response data with timing information
        """
        async with httpx.AsyncClient() as client:
            start_time = time.perf_counter()
            response = await client.post(
                self.service_url,
                json={"prompt": prompt},
                timeout=60.0,
            )
            elapsed_ms = (time.perf_counter() - start_time) * 1000

            response.raise_for_status()
            data: dict[str, Any] = response.json()

            if "total_time_ms" not in data:
                data["total_time_ms"] = elapsed_ms

            return data

    async def _measure_quality(self, quantization_format: str) -> float:
        """Measure quality for a quantization format.

        Args:
            quantization_format: The format being measured

        Returns:
            Quality score (0-1)
        """
        if self.evaluation_set_path is None:
            return await self._evaluate_quality(quantization_format)

        # Load evaluation set
        events = self._load_evaluation_set()
        return await self._run_evaluation(events)

    async def _evaluate_quality(self, _quantization_format: str) -> float:
        """Evaluate quality without evaluation set.

        Args:
            _quantization_format: The format being evaluated (unused)

        Returns:
            Quality score (0-1)
        """
        # Run a few test prompts and check for coherence
        test_prompts = [
            "Analyze: Person at front door during daytime",
            "Analyze: Vehicle in driveway at night",
            "Analyze: Motion detected in backyard",
        ]

        coherent_count = 0
        for prompt in test_prompts:
            result = await self._send_inference_request(prompt)
            response_text = result.get("response", "")
            if not detect_gibberish_output(response_text):
                coherent_count += 1

        return coherent_count / len(test_prompts)

    def _load_evaluation_set(self) -> list[dict[str, Any]]:
        """Load the evaluation set from disk.

        Returns:
            List of evaluation events
        """
        if self._evaluation_set is not None:
            return self._evaluation_set

        if self.evaluation_set_path is None:
            return []

        events_file = self.evaluation_set_path / "events.json"
        if events_file.exists():
            self._evaluation_set = json.loads(events_file.read_text())
            return self._evaluation_set

        # Load individual event files
        events = []
        for event_file in sorted(self.evaluation_set_path.glob("evt_*.json")):
            events.append(json.loads(event_file.read_text()))

        self._evaluation_set = events
        return events

    async def _run_evaluation(self, events: list[dict[str, Any]]) -> float:
        """Run quality evaluation on events.

        Args:
            events: List of evaluation events

        Returns:
            Quality score (0-1)
        """
        if not events:
            return 0.0

        correct = 0
        for event in events[:20]:  # Sample first 20 events
            result = await self._send_inference_request(event.get("prompt", ""))
            response_text = result.get("response", "")

            # Check if response is coherent
            if not detect_gibberish_output(response_text):
                correct += 1

        return correct / min(len(events), 20)


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        args: Command-line arguments (None for sys.argv)

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(description="Benchmark quantization formats for LLM inference")

    parser.add_argument(
        "--formats",
        nargs="+",
        default=QUANTIZATION_FORMATS,
        help="Quantization formats to benchmark",
    )

    parser.add_argument(
        "--baseline",
        type=str,
        default=BASELINE_FORMAT,
        help="Baseline format for comparison",
    )

    parser.add_argument(
        "--service-url",
        type=str,
        default="http://localhost:8091",
        help="URL of the LLM inference service",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/reports/quantization-comparison.md"),
        help="Output file for comparison report",
    )

    parser.add_argument(
        "--evaluation-set",
        type=Path,
        default=None,
        help="Path to evaluation set for quality measurement",
    )

    return parser.parse_args(args)


async def main() -> int:
    """Main entry point.

    Returns:
        Exit code
    """
    args = parse_args()

    benchmarker = QuantizationBenchmarker(
        service_url=args.service_url,
        evaluation_set_path=args.evaluation_set,
    )

    print(f"Benchmarking formats: {args.formats}")
    print(f"Baseline: {args.baseline}")

    # Run benchmarks
    results = []
    for fmt in args.formats:
        print(f"Benchmarking {fmt}...")
        result = await benchmarker.benchmark_format(fmt)
        results.append(result)
        print(f"  VRAM: {result['vram']['peak_mb']:.0f} MB")
        print(f"  Quality: {result['quality_score']:.1%}")

    # Generate comparison
    comparison = generate_comparison_results(results, baseline=args.baseline)

    # Select recommendation
    recommended = select_recommended_format(comparison)
    if recommended:
        comparison["recommended"] = recommended["format"]
        print(f"\nRecommended format: {recommended['format']}")

    # Save report
    save_comparison_report(comparison, args.output)
    print(f"\nReport saved to: {args.output}")

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    raise SystemExit(exit_code)
