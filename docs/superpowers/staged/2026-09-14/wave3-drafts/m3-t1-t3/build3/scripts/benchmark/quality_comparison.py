#!/usr/bin/env python3
"""Quality comparison benchmark for LLM inference engines.

Compares response quality/accuracy between different LLM engines and quantizations
using ground truth evaluation data. Measures:
- Risk score MAE (Mean Absolute Error)
- Risk level classification accuracy
- JSON validity rate
- Reasoning quality score

Usage:
    # Compare vLLM NVFP4 vs llama.cpp Q4_K_M
    python scripts/benchmark/quality_comparison.py \
        --evaluation-set data/benchmark/evaluation-set \
        --output results/benchmarks/quality_comparison.json

    # Test specific engine only
    python scripts/benchmark/quality_comparison.py \
        --engines vllm \
        --evaluation-set data/benchmark/evaluation-set
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

import httpx

from scripts.benchmark.quality import QualityScorer


class EngineType(Enum):
    """Supported LLM inference engines."""

    LLAMA_CPP = "llama.cpp"
    VLLM = "vllm"


@dataclass
class EngineQualityConfig:
    """Configuration for quality testing an LLM engine."""

    engine_type: EngineType
    service_url: str
    model_name: str
    quantization: str
    api_format: str  # "llama.cpp" or "openai"


@dataclass
class EngineQualityMetrics:
    """Quality metrics for an LLM engine."""

    engine_type: str
    model_name: str
    quantization: str
    total_samples: int
    # Core quality metrics
    average_mae: float
    mae_acceptable_rate: float  # % within +/-5
    mae_marginal_rate: float  # % within +/-10
    risk_level_accuracy: float
    json_validity_rate: float
    average_reasoning_score: float
    overall_quality: float
    # Timing metrics
    average_latency_ms: float
    total_inference_time_sec: float


@dataclass
class QualityComparisonReport:
    """Comparison report between engines."""

    comparison_date: str
    evaluation_set_size: int
    engines: list[EngineQualityMetrics]
    winner: str
    deltas: dict[str, float]
    recommendations: list[str]


# Default engine configurations for quality testing
_LLM_PORT = os.environ.get("LLM_PORT", "8091")
_VLLM_PORT = os.environ.get("VLLM_PORT", "8097")

QUALITY_ENGINE_CONFIGS: dict[EngineType, EngineQualityConfig] = {
    EngineType.LLAMA_CPP: EngineQualityConfig(
        engine_type=EngineType.LLAMA_CPP,
        service_url=f"http://localhost:{_LLM_PORT}",
        model_name="Nemotron-3-Nano-30B-A3B",
        quantization="Q4_K_M",
        api_format="llama.cpp",
    ),
    EngineType.VLLM: EngineQualityConfig(
        engine_type=EngineType.VLLM,
        service_url=f"http://localhost:{_VLLM_PORT}",
        model_name="Nemotron-3-Nano-30B-A3B",
        quantization="NVFP4",
        api_format="openai",
    ),
}


def load_evaluation_set(evaluation_set_path: Path) -> list[dict[str, Any]]:
    """Load evaluation set with ground truth data.

    Args:
        evaluation_set_path: Path to evaluation set directory

    Returns:
        List of evaluation events with prompts and expected responses
    """
    events_file = evaluation_set_path / "events.json"
    if events_file.exists():
        return json.loads(events_file.read_text())

    # Load individual event files
    events = []
    for event_file in sorted(evaluation_set_path.glob("evt_*.json")):
        events.append(json.loads(event_file.read_text()))

    return events


class QualityBenchmarker:
    """Benchmarks LLM quality against ground truth."""

    def __init__(
        self,
        configs: dict[EngineType, EngineQualityConfig] | None = None,
        timeout: float = 120.0,
    ) -> None:
        """Initialize quality benchmarker.

        Args:
            configs: Engine configurations (defaults to QUALITY_ENGINE_CONFIGS)
            timeout: Request timeout in seconds
        """
        self.configs = configs or QUALITY_ENGINE_CONFIGS
        self.timeout = timeout
        self.scorer = QualityScorer()

    async def check_engine_health(self, engine_type: EngineType) -> bool:
        """Check if an engine is healthy.

        Args:
            engine_type: Engine to check

        Returns:
            True if engine is healthy
        """
        config = self.configs.get(engine_type)
        if not config:
            return False

        health_url = f"{config.service_url}/health"
        if config.api_format == "openai":
            health_url = f"{config.service_url}/health"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(health_url, timeout=5.0)
                return response.status_code == 200
        except Exception:
            return False

    async def send_inference_request(
        self,
        config: EngineQualityConfig,
        prompt: str,
    ) -> tuple[dict[str, Any] | None, float]:
        """Send inference request to an engine.

        Args:
            config: Engine configuration
            prompt: The prompt to send

        Returns:
            Tuple of (parsed response or None, latency in ms)
        """
        start_time = time.perf_counter()

        try:
            async with httpx.AsyncClient() as client:
                if config.api_format == "openai":
                    # vLLM OpenAI-compatible API
                    response = await client.post(
                        f"{config.service_url}/v1/chat/completions",
                        json={
                            "model": config.model_name,
                            "messages": [
                                {
                                    "role": "system",
                                    "content": "You are a security analysis AI. Respond with valid JSON containing: risk_score (0-100), risk_level (low/medium/high/critical), summary, and reasoning.",
                                },
                                {"role": "user", "content": prompt},
                            ],
                            "temperature": 0.1,
                            "max_tokens": 512,
                        },
                        timeout=self.timeout,
                    )
                    response.raise_for_status()
                    data = response.json()

                    # Extract content from OpenAI format
                    content = data["choices"][0]["message"]["content"]

                    # Try to parse as JSON
                    try:
                        parsed = json.loads(content)
                    except json.JSONDecodeError:
                        # Try to extract JSON from markdown code block
                        if "```json" in content:
                            json_str = content.split("```json")[1].split("```")[0].strip()
                            parsed = json.loads(json_str)
                        elif "```" in content:
                            json_str = content.split("```")[1].split("```")[0].strip()
                            parsed = json.loads(json_str)
                        else:
                            parsed = None

                else:
                    # llama.cpp native API
                    response = await client.post(
                        f"{config.service_url}/completion",
                        json={
                            "prompt": f"<|system|>\nYou are a security analysis AI. Respond with valid JSON containing: risk_score (0-100), risk_level (low/medium/high/critical), summary, and reasoning.\n<|user|>\n{prompt}\n<|assistant|>\n",
                            "temperature": 0.1,
                            "n_predict": 512,
                            "stop": ["<|end|>", "<|user|>"],
                        },
                        timeout=self.timeout,
                    )
                    response.raise_for_status()
                    data = response.json()

                    content = data.get("content", "")

                    # Try to parse as JSON
                    try:
                        parsed = json.loads(content)
                    except json.JSONDecodeError:
                        parsed = None

                latency_ms = (time.perf_counter() - start_time) * 1000
                return parsed, latency_ms

        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            print(f"  Error: {e}")
            return None, latency_ms

    async def benchmark_engine(
        self,
        engine_type: EngineType,
        evaluation_events: list[dict[str, Any]],
        max_samples: int | None = None,
    ) -> EngineQualityMetrics | None:
        """Benchmark quality for a single engine.

        Args:
            engine_type: Engine to benchmark
            evaluation_events: List of evaluation events
            max_samples: Maximum samples to test (None = all)

        Returns:
            Quality metrics or None if engine unavailable
        """
        config = self.configs.get(engine_type)
        if not config:
            print(f"No config for {engine_type.value}")
            return None

        # Check health
        healthy = await self.check_engine_health(engine_type)
        if not healthy:
            print(f"Engine {engine_type.value} not healthy, skipping")
            return None

        print(f"\nBenchmarking {engine_type.value} ({config.quantization})...")

        # Limit samples if specified
        events = evaluation_events[:max_samples] if max_samples else evaluation_events

        # Collect responses and score
        dataset: list[tuple[dict[str, Any], dict[str, Any] | str]] = []
        latencies: list[float] = []
        total_start = time.perf_counter()

        for i, event in enumerate(events):
            prompt = event.get("prompt", "")
            expected = event.get("expected_response", {})

            print(
                f"  [{i + 1}/{len(events)}] Processing event {event.get('event_id', 'unknown')}...",
                end=" ",
            )

            response, latency_ms = await self.send_inference_request(config, prompt)
            latencies.append(latency_ms)

            if response is None:
                print(f"FAILED ({latency_ms:.0f}ms)")
                dataset.append((expected, ""))
            else:
                print(f"OK ({latency_ms:.0f}ms)")
                dataset.append((expected, response))

        total_time = time.perf_counter() - total_start

        # Score the dataset
        report = self.scorer.score_dataset(dataset)

        return EngineQualityMetrics(
            engine_type=engine_type.value,
            model_name=config.model_name,
            quantization=config.quantization,
            total_samples=report.total_samples,
            average_mae=report.average_mae,
            mae_acceptable_rate=report.mae_acceptable_rate,
            mae_marginal_rate=report.mae_marginal_rate,
            risk_level_accuracy=report.risk_level_accuracy,
            json_validity_rate=report.json_validity_rate,
            average_reasoning_score=report.average_reasoning_score,
            overall_quality=report.overall_quality,
            average_latency_ms=sum(latencies) / len(latencies) if latencies else 0,
            total_inference_time_sec=total_time,
        )

    async def compare_engines(
        self,
        evaluation_events: list[dict[str, Any]],
        engines: list[str] | None = None,
        max_samples: int | None = None,
    ) -> QualityComparisonReport:
        """Compare quality across engines.

        Args:
            evaluation_events: List of evaluation events
            engines: List of engine names to test (None = all)
            max_samples: Maximum samples per engine

        Returns:
            Comparison report
        """
        # Filter engines if specified
        engine_types = list(self.configs.keys())
        if engines:
            engine_set = set(engines)
            engine_types = [e for e in engine_types if e.value in engine_set]

        # Benchmark each engine
        results: list[EngineQualityMetrics] = []
        for engine_type in engine_types:
            metrics = await self.benchmark_engine(engine_type, evaluation_events, max_samples)
            if metrics:
                results.append(metrics)

        if not results:
            raise RuntimeError("No engines available for benchmarking")

        # Determine winner and calculate deltas
        winner = max(results, key=lambda x: x.overall_quality)
        deltas = {}
        recommendations = []

        if len(results) == 2:
            a, b = results
            deltas = {
                "mae_delta": a.average_mae - b.average_mae,
                "risk_accuracy_delta_pct": (a.risk_level_accuracy - b.risk_level_accuracy) * 100,
                "json_validity_delta_pct": (a.json_validity_rate - b.json_validity_rate) * 100,
                "overall_quality_delta_pct": (a.overall_quality - b.overall_quality) * 100,
                "latency_delta_ms": a.average_latency_ms - b.average_latency_ms,
            }

            # Generate recommendations
            if abs(deltas["overall_quality_delta_pct"]) < 2:
                recommendations.append("Quality is comparable between engines (<2% difference)")
            else:
                recommendations.append(
                    f"{winner.engine_type} has {abs(deltas['overall_quality_delta_pct']):.1f}% better overall quality"
                )

            if abs(deltas["mae_delta"]) < 3:
                recommendations.append("Risk score accuracy is similar (MAE within 3 points)")
            else:
                better = a if a.average_mae < b.average_mae else b
                recommendations.append(
                    f"{better.engine_type} has {abs(deltas['mae_delta']):.1f} points lower MAE"
                )

            faster = a if a.average_latency_ms < b.average_latency_ms else b
            speedup = max(a.average_latency_ms, b.average_latency_ms) / min(
                a.average_latency_ms, b.average_latency_ms
            )
            recommendations.append(f"{faster.engine_type} is {speedup:.1f}x faster")

        return QualityComparisonReport(
            comparison_date=datetime.now(UTC).isoformat(),
            evaluation_set_size=len(evaluation_events),
            engines=[asdict(r) for r in results],
            winner=winner.engine_type,
            deltas=deltas,
            recommendations=recommendations,
        )


def save_report(report: QualityComparisonReport, output_path: Path) -> None:
    """Save comparison report to JSON file.

    Args:
        report: The comparison report
        output_path: Output file path
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(report), indent=2))
    print(f"\nReport saved to: {output_path}")


def print_report(report: QualityComparisonReport) -> None:
    """Print comparison report to console.

    Args:
        report: The comparison report
    """
    print("\n" + "=" * 70)
    print("QUALITY COMPARISON REPORT")
    print("=" * 70)
    print(f"Date: {report.comparison_date}")
    print(f"Evaluation samples: {report.evaluation_set_size}")
    print(f"Winner: {report.winner}")
    print()

    # Print engine results
    print("-" * 70)
    print(f"{'Metric':<30} ", end="")
    for engine in report.engines:
        print(f"{engine['engine_type']:>18} ", end="")
    print()
    print("-" * 70)

    metrics_to_show = [
        ("Quantization", "quantization", ""),
        ("Overall Quality", "overall_quality", ".1%"),
        ("Risk Score MAE", "average_mae", ".2f"),
        ("MAE Acceptable (±5)", "mae_acceptable_rate", ".1%"),
        ("MAE Marginal (±10)", "mae_marginal_rate", ".1%"),
        ("Risk Level Accuracy", "risk_level_accuracy", ".1%"),
        ("JSON Validity Rate", "json_validity_rate", ".1%"),
        ("Reasoning Score", "average_reasoning_score", ".2f"),
        ("Avg Latency (ms)", "average_latency_ms", ".0f"),
    ]

    for label, key, fmt in metrics_to_show:
        print(f"{label:<30} ", end="")
        for engine in report.engines:
            val = engine.get(key, "N/A")
            if isinstance(val, float):
                if "%" in fmt:
                    print(f"{val:{fmt.replace('%', '')}%:>18} ", end="")
                else:
                    print(f"{val:{fmt}:>18} ", end="")
            else:
                print(f"{val:>18} ", end="")
        print()

    print("-" * 70)

    # Print recommendations
    if report.recommendations:
        print("\nRecommendations:")
        for rec in report.recommendations:
            print(f"  • {rec}")

    print("=" * 70)


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Compare LLM quality across engines and quantizations"
    )

    parser.add_argument(
        "--evaluation-set",
        type=Path,
        default=Path("data/benchmark/evaluation-set"),
        help="Path to evaluation set directory",
    )

    parser.add_argument(
        "--engines",
        nargs="+",
        choices=["llama.cpp", "vllm"],
        default=None,
        help="Engines to benchmark (default: all available)",
    )

    parser.add_argument(
        "--max-samples",
        type=int,
        default=None,
        help="Maximum samples to test per engine (default: all)",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/benchmarks/quality_comparison.json"),
        help="Output file for comparison report",
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="Request timeout in seconds",
    )

    return parser.parse_args(args)


async def main() -> int:
    """Main entry point."""
    args = parse_args()

    # Load evaluation set
    print(f"Loading evaluation set from: {args.evaluation_set}")
    events = load_evaluation_set(args.evaluation_set)
    print(f"Loaded {len(events)} evaluation events")

    if not events:
        print("Error: No evaluation events found")
        return 1

    # Run comparison
    benchmarker = QualityBenchmarker(timeout=args.timeout)
    report = await benchmarker.compare_engines(
        events,
        engines=args.engines,
        max_samples=args.max_samples,
    )

    # Print and save report
    print_report(report)
    save_report(report, args.output)

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    raise SystemExit(exit_code)
