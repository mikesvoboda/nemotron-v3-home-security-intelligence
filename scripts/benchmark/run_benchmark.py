#!/usr/bin/env python3
"""Benchmark orchestrator for LLM performance testing.

This module orchestrates benchmark scenarios:
- Single request latency: One request at a time, measure response time
- Sustained load: Continuous requests at configurable rate
- Burst handling: Simulate 10+ simultaneous detections
- Cold start: Time from service start to first successful inference

Usage:
    python scripts/benchmark/run_benchmark.py \\
        --evaluation-set data/benchmark/evaluation-set/ \\
        --llm-endpoint http://localhost:8091 \\
        --output results/benchmarks/ \\
        --scenarios single sustained burst cold_start
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from scripts.benchmark.metrics import MetricsCollector


@dataclass
class BenchmarkConfig:
    """Configuration for benchmark execution.

    Attributes:
        llm_endpoint: URL of the LLM service to benchmark
        evaluation_set_path: Path to directory containing evaluation events
        output_path: Path to save benchmark results
        scenarios: List of scenarios to run (single, sustained, burst, cold_start)
        sustained_duration_sec: Duration for sustained load test in seconds
        sustained_rate: Requests per minute for sustained load
        burst_size: Number of concurrent requests for burst test
        cold_start_attempts: Number of cold start attempts to measure
    """

    llm_endpoint: str
    evaluation_set_path: Path
    output_path: Path
    scenarios: list[str] = field(
        default_factory=lambda: ["single", "sustained", "burst", "cold_start"]
    )
    sustained_duration_sec: float = 60.0
    sustained_rate: int = 10
    burst_size: int = 10
    cold_start_attempts: int = 3

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        # Validate llm_endpoint is a valid URL
        if not self.llm_endpoint.startswith(("http://", "https://")):
            raise ValueError(
                f"Invalid endpoint URL: {self.llm_endpoint}. Must start with http:// or https://"
            )

        # Validate evaluation_set_path exists
        if not self.evaluation_set_path.exists():
            raise FileNotFoundError(
                f"Evaluation set path does not exist: {self.evaluation_set_path}"
            )


@dataclass
class BenchmarkResults:
    """Results from benchmark execution.

    Attributes:
        metadata: Benchmark metadata (timestamp, config, etc.)
        scenarios: List of scenario results
        summary: Aggregate summary statistics
    """

    metadata: dict[str, Any]
    scenarios: list[dict[str, Any]]
    summary: dict[str, Any]


class QualityScorer:
    """Scores LLM response quality against expected outputs.

    This class provides methods to:
    - Score individual responses for accuracy, relevance, coherence
    - Aggregate scores across multiple responses
    - Compare against baseline metrics
    """

    def __init__(self) -> None:
        """Initialize quality scorer."""
        self._scores: list[dict[str, float]] = []

    def score_response(
        self, response: str, expected: str | dict[str, Any], _context: dict[str, Any]
    ) -> dict[str, float]:
        """Score a single LLM response.

        Args:
            response: The LLM's response
            expected: The expected response (string or dict with summary/reasoning)
            _context: Additional context for scoring (unused)

        Returns:
            Dictionary with accuracy, relevance, coherence, and overall scores
        """
        # Handle dict expected responses (extract summary + reasoning)
        if isinstance(expected, dict):
            expected_parts = []
            if "summary" in expected:
                expected_parts.append(str(expected["summary"]))
            if "reasoning" in expected:
                expected_parts.append(str(expected["reasoning"]))
            expected = " ".join(expected_parts) if expected_parts else str(expected)

        # Simple scoring based on string similarity
        # In production, this would use more sophisticated metrics
        response_lower = str(response).lower()
        expected_lower = str(expected).lower()

        # Calculate basic similarity scores
        if response_lower == expected_lower:
            accuracy = 1.0
        elif expected_lower in response_lower or response_lower in expected_lower:
            accuracy = 0.8
        else:
            # Basic word overlap
            response_words = set(response_lower.split())
            expected_words = set(expected_lower.split())
            if expected_words:
                overlap = len(response_words & expected_words) / len(expected_words)
                accuracy = max(0.3, min(0.9, overlap))
            else:
                accuracy = 0.5

        relevance = min(1.0, accuracy + 0.1)
        coherence = 0.85 if len(response) > 10 else 0.5
        overall = (accuracy + relevance + coherence) / 3

        scores = {
            "accuracy": round(accuracy, 2),
            "relevance": round(relevance, 2),
            "coherence": round(coherence, 2),
            "overall": round(overall, 2),
        }
        self._scores.append(scores)
        return scores

    def aggregate_scores(self, scores: list[dict[str, float]]) -> dict[str, float]:
        """Aggregate multiple quality scores.

        Args:
            scores: List of individual quality score dictionaries

        Returns:
            Dictionary with mean scores and overall quality
        """
        if not scores:
            return {
                "mean_accuracy": 0.0,
                "mean_relevance": 0.0,
                "mean_coherence": 0.0,
                "overall_quality": 0.0,
            }

        mean_accuracy = sum(s["accuracy"] for s in scores) / len(scores)
        mean_relevance = sum(s["relevance"] for s in scores) / len(scores)
        mean_coherence = sum(s["coherence"] for s in scores) / len(scores)
        overall_quality = (mean_accuracy + mean_relevance + mean_coherence) / 3

        return {
            "mean_accuracy": round(mean_accuracy, 2),
            "mean_relevance": round(mean_relevance, 2),
            "mean_coherence": round(mean_coherence, 2),
            "overall_quality": round(overall_quality, 2),
        }


class BenchmarkRunner:
    """Orchestrates benchmark scenario execution.

    This class coordinates:
    - Loading the evaluation set
    - Running configured scenarios
    - Collecting metrics via MetricsCollector
    - Scoring quality via QualityScorer
    - Saving results to JSON
    """

    def __init__(
        self,
        config: BenchmarkConfig,
        metrics_collector: MetricsCollector,
        quality_scorer: QualityScorer,
    ):
        """Initialize benchmark runner.

        Args:
            config: Benchmark configuration
            metrics_collector: Metrics collector instance
            quality_scorer: Quality scorer instance
        """
        self.config = config
        self.metrics_collector = metrics_collector
        self.quality_scorer = quality_scorer
        self.events: list[dict[str, Any]] = []

    async def load_evaluation_set(self) -> list[dict[str, Any]]:
        """Load the 100-event evaluation set from disk.

        Returns:
            List of evaluation events with prompts and expected responses

        Raises:
            ValueError: If no events found or directory is empty
            FileNotFoundError: If evaluation set path does not exist
        """
        eval_path = self.config.evaluation_set_path

        if not eval_path.exists():
            raise FileNotFoundError(f"Evaluation set path does not exist: {eval_path}")

        # Load individual event files (evt_*.json), skip combined events.json
        events = []
        json_files = sorted(eval_path.glob("evt_*.json"))

        for json_file in json_files:
            event_data = json.loads(json_file.read_text())
            events.append(event_data)

        if not events:
            raise ValueError(f"No events found in evaluation set: {eval_path}")

        self.events = events
        return events

    async def run_single_request_scenario(self) -> dict[str, Any]:
        """Run single request latency scenario.

        Sends one request at a time and measures response time.
        Uses the first event from the evaluation set.

        Returns:
            Dictionary with scenario results including latency metrics and quality scores
        """
        # Load events if not already loaded
        if not self.events:
            await self.load_evaluation_set()

        # Use the first event
        first_event = self.events[0]
        prompt = first_event.get("prompt", "")
        expected = first_event.get("expected_response", "")
        context = first_event.get("context", {})

        # Record the request
        response = await self.metrics_collector.record_request(prompt)

        # Get latency metrics
        latency_metrics = self.metrics_collector.get_latency_metrics()

        # Score response quality (LLM returns 'content', fallback to 'response')
        response_text = response.get("content", response.get("response", ""))
        quality_scores = self.quality_scorer.score_response(response_text, expected, context)

        return {
            "scenario": "single_request",
            "latency_metrics": {
                "p50": latency_metrics.p50,
                "p95": latency_metrics.p95,
                "p99": latency_metrics.p99,
                "time_to_first_token": latency_metrics.time_to_first_token,
                "mean": latency_metrics.mean,
            },
            "quality_scores": quality_scores,
        }

    async def run_sustained_load_scenario(self) -> dict[str, Any]:
        """Run sustained load scenario.

        Sends continuous requests at configured rate for configured duration.
        Cycles through all evaluation set events.

        Returns:
            Dictionary with scenario results including throughput metrics
        """
        # Load events if not already loaded
        if not self.events:
            await self.load_evaluation_set()

        # Extract prompts from all events
        prompts = [event.get("prompt", "") for event in self.events]

        # Run sustained load test
        throughput_metrics = await self.metrics_collector.run_sustained_load(
            prompts=prompts,
            duration_sec=self.config.sustained_duration_sec,
        )

        return {
            "scenario": "sustained_load",
            "throughput_metrics": {
                "requests_per_min": throughput_metrics.requests_per_min,
                "tokens_per_sec": throughput_metrics.tokens_per_sec,
                "total_requests": throughput_metrics.total_requests,
                "total_tokens": throughput_metrics.total_tokens,
                "duration_sec": throughput_metrics.duration_sec,
            },
        }

    async def run_burst_scenario(self) -> dict[str, Any]:
        """Run burst handling scenario.

        Sends multiple concurrent requests simultaneously (default 10).
        Measures how the service handles sudden load spikes.

        Returns:
            Dictionary with scenario results including latency under burst and failure count
        """
        # Load events if not already loaded
        if not self.events:
            await self.load_evaluation_set()

        burst_size = self.config.burst_size
        failures = 0

        # Create tasks for concurrent requests
        tasks = []
        for i in range(burst_size):
            event = self.events[i % len(self.events)]
            prompt = event.get("prompt", "")
            tasks.append(self.metrics_collector.record_request(prompt))

        # Run all requests concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Count failures
        for result in results:
            if isinstance(result, Exception):
                failures += 1

        # Get latency metrics
        latency_metrics = self.metrics_collector.get_latency_metrics()

        return {
            "scenario": "burst_handling",
            "burst_size": burst_size,
            "latency_metrics": {
                "p50": latency_metrics.p50,
                "p95": latency_metrics.p95,
                "p99": latency_metrics.p99,
                "time_to_first_token": latency_metrics.time_to_first_token,
                "mean": latency_metrics.mean,
            },
            "failures": failures,
        }

    async def run_cold_start_scenario(self) -> dict[str, Any]:
        """Run cold start timing scenario.

        Measures time from service start to first successful inference.
        Includes health check polling and first inference timing.

        Returns:
            Dictionary with scenario results including cold start time and time to first inference
        """
        # Load events if not already loaded
        if not self.events:
            await self.load_evaluation_set()

        attempts = self.config.cold_start_attempts
        health_endpoint = f"{self.config.llm_endpoint}/health"

        start_time = time.monotonic()
        ready = False

        # Poll health endpoint until ready
        async with httpx.AsyncClient() as client:
            for _attempt in range(attempts):
                try:
                    response = await client.get(health_endpoint)
                    if response.status_code == 200:
                        ready = True
                        break
                except httpx.RequestError:
                    pass
                await asyncio.sleep(0.1)  # Small delay between attempts

        cold_start_time = time.monotonic() - start_time

        # Run first inference to measure time to first inference
        inference_start = time.monotonic()
        first_event = self.events[0]
        prompt = first_event.get("prompt", "")
        await self.metrics_collector.record_request(prompt)
        time_to_first_inference = time.monotonic() - inference_start

        return {
            "scenario": "cold_start",
            "cold_start_time": cold_start_time,
            "time_to_first_inference": time_to_first_inference,
            "attempts": attempts,
            "service_ready": ready,
        }

    async def run_all_scenarios(self) -> dict[str, Any]:
        """Run all configured scenarios.

        Returns:
            Dictionary with results from all scenarios plus metadata
        """
        # Load events if not already loaded
        if not self.events:
            await self.load_evaluation_set()

        scenario_results = []

        # Map scenario names to methods
        scenario_map = {
            "single": self.run_single_request_scenario,
            "sustained": self.run_sustained_load_scenario,
            "burst": self.run_burst_scenario,
            "cold_start": self.run_cold_start_scenario,
        }

        for scenario_name in self.config.scenarios:
            if scenario_name in scenario_map:
                result = await scenario_map[scenario_name]()
                scenario_results.append(result)

        # Build metadata
        metadata = {
            "timestamp": datetime.now(UTC).isoformat(),
            "llm_endpoint": self.config.llm_endpoint,
            "evaluation_set_size": len(self.events),
        }

        return {
            "metadata": metadata,
            "scenarios": scenario_results,
        }

    async def save_results(self, results: BenchmarkResults) -> Path:
        """Save benchmark results to JSON file.

        Creates output directory if it doesn't exist.
        Generates timestamped filename for uniqueness.

        Args:
            results: Benchmark results to save

        Returns:
            Path to the saved JSON file
        """
        # Create output directory if needed
        output_dir = self.config.output_path
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate timestamped filename
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        filename = f"benchmark_{timestamp}.json"
        output_file = output_dir / filename

        # Convert results to dict
        results_dict = {
            "metadata": results.metadata,
            "scenarios": results.scenarios,
            "summary": results.summary,
        }

        # Write JSON file
        output_file.write_text(json.dumps(results_dict, indent=2))

        return output_file


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        args: Command-line arguments (None = use sys.argv)

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="Benchmark orchestrator for LLM performance testing",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--evaluation-set",
        type=Path,
        required=True,
        help="Path to directory containing evaluation events (100-event set)",
    )

    parser.add_argument(
        "--llm-endpoint",
        type=str,
        default="http://localhost:8091",
        help="URL of the LLM service to benchmark",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/benchmarks"),
        help="Path to save benchmark results",
    )

    parser.add_argument(
        "--scenarios",
        nargs="+",
        choices=["single", "sustained", "burst", "cold_start"],
        default=["single", "sustained", "burst", "cold_start"],
        help="Scenarios to run",
    )

    parser.add_argument(
        "--sustained-duration",
        type=int,
        default=60,
        help="Duration for sustained load test in seconds",
    )

    parser.add_argument(
        "--sustained-rate",
        type=int,
        default=10,
        help="Requests per minute for sustained load test",
    )

    parser.add_argument(
        "--burst-size",
        type=int,
        default=10,
        help="Number of concurrent requests for burst test",
    )

    parser.add_argument(
        "--cold-start-attempts",
        type=int,
        default=3,
        help="Number of cold start attempts to measure",
    )

    return parser.parse_args(args)


async def main() -> int:
    """Main entry point for benchmark orchestrator.

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    args = parse_args()

    # Create configuration
    config = BenchmarkConfig(
        llm_endpoint=args.llm_endpoint,
        evaluation_set_path=args.evaluation_set,
        output_path=args.output,
        scenarios=args.scenarios,
        sustained_duration_sec=float(args.sustained_duration),
        sustained_rate=args.sustained_rate,
        burst_size=args.burst_size,
        cold_start_attempts=args.cold_start_attempts,
    )

    # Initialize components
    metrics_collector = MetricsCollector(service_url=config.llm_endpoint)
    quality_scorer = QualityScorer()

    # Create runner and execute
    runner = BenchmarkRunner(
        config=config,
        metrics_collector=metrics_collector,
        quality_scorer=quality_scorer,
    )

    print(f"Loading evaluation set from {config.evaluation_set_path}...")
    await runner.load_evaluation_set()

    print(f"Running scenarios: {', '.join(config.scenarios)}...")
    results_dict = await runner.run_all_scenarios()

    results = BenchmarkResults(
        metadata=results_dict["metadata"],
        scenarios=results_dict["scenarios"],
        summary=results_dict.get("summary", {}),
    )

    output_file = await runner.save_results(results)
    print(f"Results saved to {output_file}")

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    raise SystemExit(exit_code)
