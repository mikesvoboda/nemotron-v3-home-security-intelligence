"""Engine comparison module for LLM performance benchmarking.

This module provides functionality to compare different LLM inference engines:
- llama.cpp (current default)
- vLLM (optional, for comparison)

Usage:
    python scripts/benchmark/engine_comparison.py \\
        --prompts "Test prompt" \\
        --engines llama.cpp vllm \\
        --output results/engine_comparison.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import httpx
import numpy as np


class EngineType(Enum):
    """Supported LLM inference engines."""

    LLAMA_CPP = "llama.cpp"
    VLLM = "vllm"


@dataclass
class EngineConfig:
    """Configuration for an LLM inference engine."""

    engine_type: EngineType
    service_url: str
    model_path: str
    api_format: str
    gpu_memory_utilization: float | None = None
    tensor_parallel_size: int | None = None
    max_model_len: int | None = None


@dataclass
class EngineMetrics:
    """Performance metrics for an LLM inference engine."""

    engine_type: EngineType
    latency_p50_ms: float
    latency_p95_ms: float
    latency_p99_ms: float
    throughput_tokens_per_sec: float
    vram_peak_mb: float
    vram_steady_mb: float
    time_to_first_token_ms: float
    requests_per_minute: float


# Default engine configurations
# Ports read from environment variables (.env is single source of truth)
_LLM_PORT = os.environ.get("LLM_PORT", "8091")
_VLLM_PORT = os.environ.get("VLLM_PORT", "8097")

ENGINE_CONFIGS: dict[EngineType, EngineConfig] = {
    EngineType.LLAMA_CPP: EngineConfig(
        engine_type=EngineType.LLAMA_CPP,
        service_url=f"http://localhost:{_LLM_PORT}",
        model_path="/models/nemotron",
        api_format="llama.cpp",
    ),
    EngineType.VLLM: EngineConfig(
        engine_type=EngineType.VLLM,
        service_url=f"http://localhost:{_VLLM_PORT}",
        model_path=os.environ.get("VLLM_MODEL", "nvidia/Nemotron-Mini-4B-Instruct"),
        api_format="openai",
        gpu_memory_utilization=float(os.environ.get("VLLM_GPU_MEMORY_UTILIZATION", "0.9")),
        tensor_parallel_size=1,
        max_model_len=int(os.environ.get("VLLM_MAX_MODEL_LEN", "32768")),
    ),
}


class EngineComparator:
    """Compares performance across LLM inference engines."""

    def __init__(self, configs: dict[EngineType, EngineConfig] | None = None) -> None:
        """Initialize engine comparator."""
        self.configs = configs or ENGINE_CONFIGS

    async def check_engine_health(self, engine_type: EngineType) -> bool:
        """Check if an engine is healthy and responding.

        Args:
            engine_type: The engine type to check.

        Returns:
            True if engine is healthy, False otherwise.
        """
        config = self.configs[engine_type]
        health_url = f"{config.service_url}/health"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(health_url, timeout=10.0)
                return response.status_code == 200
        except Exception:
            return False

    async def benchmark_engine(self, engine_type: EngineType, prompts: list[str]) -> EngineMetrics:
        """Benchmark a single engine.

        Args:
            engine_type: The engine type to benchmark.
            prompts: List of prompts to use for benchmarking.

        Returns:
            EngineMetrics with benchmark results.

        Raises:
            ValueError: If prompts list is empty.
            RuntimeError: If engine is not healthy.
            KeyError: If engine config is not found.
        """
        if not prompts:
            raise ValueError("Prompts list cannot be empty")

        if engine_type not in self.configs:
            raise KeyError(f"Engine config not found for {engine_type}")

        is_healthy = await self.check_engine_health(engine_type)
        if not is_healthy:
            raise RuntimeError(f"Engine {engine_type.value} is not healthy")

        return await self._run_benchmark(engine_type, prompts)

    async def compare_all_engines(
        self,
        prompts: list[str],
        skip_unavailable: bool = False,
    ) -> dict[EngineType, EngineMetrics]:
        """Compare all configured engines.

        Args:
            prompts: List of prompts to use for benchmarking.
            skip_unavailable: If True, skip engines that aren't available.

        Returns:
            Dictionary mapping engine types to their metrics.
        """
        results: dict[EngineType, EngineMetrics] = {}

        for engine_type in self.configs:
            try:
                metrics = await self.benchmark_engine(engine_type, prompts)
                results[engine_type] = metrics
            except RuntimeError:
                if not skip_unavailable:
                    raise
                # Skip this engine if unavailable
                continue

        return results

    async def _run_benchmark(self, engine_type: EngineType, prompts: list[str]) -> EngineMetrics:
        """Run benchmark for a single engine.

        Args:
            engine_type: The engine type to benchmark.
            prompts: List of prompts to use.

        Returns:
            EngineMetrics with collected measurements.
        """
        config = self.configs[engine_type]
        latencies: list[float] = []
        ttft_values: list[float] = []
        total_tokens = 0
        start_time = time.perf_counter()

        # Collect latency and token measurements
        async with httpx.AsyncClient() as client:
            for prompt in prompts:
                request_data = self._format_request(engine_type, prompt)

                # Determine endpoint
                if config.api_format == "openai":
                    endpoint = f"{config.service_url}/v1/chat/completions"
                else:
                    endpoint = f"{config.service_url}/completion"

                request_start = time.perf_counter()
                try:
                    response = await client.post(
                        endpoint,
                        json=request_data,
                        timeout=60.0,
                    )
                    response.raise_for_status()
                    data = response.json()

                    elapsed_ms = (time.perf_counter() - request_start) * 1000
                    latencies.append(elapsed_ms)

                    # Parse response
                    parsed = self._parse_response(engine_type, data)
                    total_tokens += parsed.get("tokens", 0)

                    # Estimate TTFT as ~30% of total time if not provided
                    ttft_ms = parsed.get("ttft_ms", elapsed_ms * 0.3)
                    ttft_values.append(ttft_ms)

                except httpx.TimeoutException as e:
                    raise TimeoutError(f"Request to {engine_type.value} timed out") from e

        duration_sec = time.perf_counter() - start_time

        # Calculate metrics
        percentiles = self._calculate_latency_percentiles(latencies)
        throughput = self._calculate_throughput(total_tokens, duration_sec)
        requests_per_min = (len(prompts) / duration_sec) * 60

        # Get VRAM metrics (simplified - actual implementation would poll nvidia-smi)
        vram_data = await self._monitor_vram(duration_sec=1.0)

        return EngineMetrics(
            engine_type=engine_type,
            latency_p50_ms=percentiles["p50"],
            latency_p95_ms=percentiles["p95"],
            latency_p99_ms=percentiles["p99"],
            throughput_tokens_per_sec=throughput,
            vram_peak_mb=vram_data.get("peak_mb", 0.0),
            vram_steady_mb=vram_data.get("steady_mb", 0.0),
            time_to_first_token_ms=float(np.mean(ttft_values)) if ttft_values else 0.0,
            requests_per_minute=requests_per_min,
        )

    def _format_request(
        self,
        engine_type: EngineType,
        prompt: str,
        max_tokens: int = 100,
    ) -> dict[str, Any]:
        """Format request for specific engine API.

        Args:
            engine_type: The engine type.
            prompt: The prompt text.
            max_tokens: Maximum tokens to generate.

        Returns:
            Formatted request dictionary.
        """
        config = self.configs[engine_type]

        if config.api_format == "openai":
            # vLLM uses OpenAI-compatible format
            return {
                "model": config.model_path,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
            }
        else:
            # llama.cpp format
            return {
                "prompt": prompt,
                "n_predict": max_tokens,
                "stream": False,
            }

    def _parse_response(self, engine_type: EngineType, response: dict[str, Any]) -> dict[str, Any]:
        """Parse response from specific engine API.

        Args:
            engine_type: The engine type.
            response: Raw response dictionary.

        Returns:
            Parsed response with standardized fields.
        """
        config = self.configs[engine_type]

        if config.api_format == "openai":
            # vLLM (OpenAI format)
            choices = response.get("choices", [])
            text = ""
            if choices and "message" in choices[0]:
                text = choices[0]["message"].get("content", "")

            usage = response.get("usage", {})
            tokens = usage.get("completion_tokens", 0)

            return {"text": text, "tokens": tokens}
        else:
            # llama.cpp format
            text = response.get("content", "")
            tokens = response.get("tokens_predicted", 0)

            return {"text": text, "tokens": tokens}

    def _calculate_latency_percentiles(self, response_times: list[float]) -> dict[str, float]:
        """Calculate latency percentiles from response times.

        Args:
            response_times: List of response times in milliseconds.

        Returns:
            Dictionary with p50, p95, p99 percentiles.
        """
        if not response_times:
            return {"p50": 0.0, "p95": 0.0, "p99": 0.0}

        arr = np.array(response_times)
        return {
            "p50": float(np.percentile(arr, 50)),
            "p95": float(np.percentile(arr, 95)),
            "p99": float(np.percentile(arr, 99)),
        }

    def _calculate_throughput(self, total_tokens: int, duration_sec: float) -> float:
        """Calculate tokens per second throughput.

        Args:
            total_tokens: Total tokens generated.
            duration_sec: Duration in seconds.

        Returns:
            Tokens per second.
        """
        if duration_sec <= 0:
            return 0.0
        return total_tokens / duration_sec

    async def _monitor_vram(self, duration_sec: float) -> dict[str, float]:
        """Monitor VRAM usage during benchmarking.

        Args:
            duration_sec: Duration to monitor in seconds.

        Returns:
            Dictionary with peak_mb and steady_mb values.
        """
        vram_samples: list[float] = []
        start_time = time.perf_counter()

        while (time.perf_counter() - start_time) < duration_sec:
            try:
                process = await asyncio.create_subprocess_exec(
                    "nvidia-smi",
                    "--query-gpu=memory.used",
                    "--format=csv,noheader,nounits",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await process.communicate()

                if process.returncode == 0:
                    output = stdout.decode().strip()
                    for line in output.split("\n"):
                        stripped = line.strip().replace("MiB", "").strip()
                        if stripped:
                            try:
                                vram_samples.append(float(stripped))
                            except ValueError:
                                continue

            except (FileNotFoundError, OSError):
                # nvidia-smi not available
                break

            await asyncio.sleep(0.1)

        if not vram_samples:
            return {"peak_mb": 0.0, "steady_mb": 0.0}

        return {
            "peak_mb": float(np.max(vram_samples)),
            "steady_mb": float(np.median(vram_samples)),
        }


def generate_comparison_report(
    results: dict[EngineType, EngineMetrics],
) -> dict[str, Any]:
    """Generate a comparison report from benchmark results.

    Args:
        results: Dictionary mapping engine types to their metrics.

    Returns:
        Comparison report dictionary.
    """
    if not results:
        return {
            "comparison": {},
            "summary": {"note": "No engines benchmarked"},
            "recommendations": {},
        }

    comparison: dict[str, dict[str, float]] = {}
    for engine_type, metrics in results.items():
        comparison[engine_type.value] = {
            "latency_p50_ms": metrics.latency_p50_ms,
            "latency_p95_ms": metrics.latency_p95_ms,
            "latency_p99_ms": metrics.latency_p99_ms,
            "throughput_tokens_per_sec": metrics.throughput_tokens_per_sec,
            "vram_peak_mb": metrics.vram_peak_mb,
            "vram_steady_mb": metrics.vram_steady_mb,
            "time_to_first_token_ms": metrics.time_to_first_token_ms,
            "requests_per_minute": metrics.requests_per_minute,
        }

    # Calculate deltas if we have multiple engines
    deltas: dict[str, float] = {}
    recommendations: dict[str, str] = {}

    engine_list = list(results.keys())
    if len(engine_list) >= 2:
        # Compare first two engines
        e1, e2 = engine_list[0], engine_list[1]
        m1, m2 = results[e1], results[e2]

        deltas = {
            "latency_p50_delta_pct": _calc_delta_pct(m1.latency_p50_ms, m2.latency_p50_ms),
            "latency_p95_delta_pct": _calc_delta_pct(m1.latency_p95_ms, m2.latency_p95_ms),
            "throughput_delta_pct": _calc_delta_pct(
                m1.throughput_tokens_per_sec, m2.throughput_tokens_per_sec
            ),
            "vram_delta_pct": _calc_delta_pct(m1.vram_peak_mb, m2.vram_peak_mb),
        }

        # Determine best engine for each category
        recommendations = {
            "lowest_latency": e1.value if m1.latency_p50_ms <= m2.latency_p50_ms else e2.value,
            "highest_throughput": (
                e1.value
                if m1.throughput_tokens_per_sec >= m2.throughput_tokens_per_sec
                else e2.value
            ),
            "lowest_vram": e1.value if m1.vram_peak_mb <= m2.vram_peak_mb else e2.value,
            "best_ttft": (
                e1.value if m1.time_to_first_token_ms <= m2.time_to_first_token_ms else e2.value
            ),
        }

    return {
        "comparison": comparison,
        "deltas": deltas,
        "summary": {
            "engines_compared": len(results),
            "engine_names": [e.value for e in results],
        },
        "recommendations": recommendations,
    }


def _calc_delta_pct(val1: float, val2: float) -> float:
    """Calculate percentage delta between two values.

    Args:
        val1: First value.
        val2: Second value.

    Returns:
        Percentage delta (positive if val2 > val1).
    """
    if val1 == 0:
        return 0.0
    return ((val2 - val1) / val1) * 100


async def compare_engines(
    prompts: list[str],
    output_path: Path | None = None,
    engines: list[str] | None = None,
) -> dict[EngineType, EngineMetrics]:
    """Convenience function to compare engines.

    Args:
        prompts: List of prompts for benchmarking.
        output_path: Optional path to save results.
        engines: Optional list of engine names to compare.

    Returns:
        Dictionary mapping engine types to their metrics.
    """
    # Filter configs if specific engines requested
    configs = ENGINE_CONFIGS
    if engines:
        engine_set = set(engines)
        configs = {k: v for k, v in ENGINE_CONFIGS.items() if k.value in engine_set}

    comparator = EngineComparator(configs)
    results = await comparator.compare_all_engines(prompts, skip_unavailable=True)

    if output_path:
        report = generate_comparison_report(results)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2))

    return results


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        args: Command-line arguments (None = use sys.argv).

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        description="Compare LLM inference engine performance",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--prompts",
        nargs="+",
        help="Prompts to use for benchmarking",
    )

    parser.add_argument(
        "--evaluation-set",
        type=Path,
        dest="evaluation_set",
        help="Path to evaluation set directory",
    )

    parser.add_argument(
        "--output",
        type=Path,
        help="Path to save comparison results",
    )

    parser.add_argument(
        "--engines",
        nargs="+",
        choices=["llama.cpp", "vllm"],
        default=["llama.cpp", "vllm"],
        help="Engines to compare",
    )

    return parser.parse_args(args)


async def main() -> int:
    """Main entry point for engine comparison.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    args = parse_args()

    prompts = args.prompts or []

    # Load prompts from evaluation set if provided
    if args.evaluation_set and args.evaluation_set.exists():
        for json_file in sorted(args.evaluation_set.glob("*.json")):
            data = json.loads(json_file.read_text())
            if "prompt" in data:
                prompts.append(data["prompt"])

    if not prompts:
        print("Error: No prompts provided. Use --prompts or --evaluation-set")
        return 1

    print(f"Comparing engines: {', '.join(args.engines)}")
    print(f"Using {len(prompts)} prompts")

    results = await compare_engines(
        prompts=prompts,
        output_path=args.output,
        engines=args.engines,
    )

    # Print summary
    report = generate_comparison_report(results)
    print("\n=== Engine Comparison Results ===")
    for engine_name, metrics in report["comparison"].items():
        print(f"\n{engine_name}:")
        for key, value in metrics.items():
            print(f"  {key}: {value:.2f}")

    if report["recommendations"]:
        print("\n=== Recommendations ===")
        for category, winner in report["recommendations"].items():
            print(f"  {category}: {winner}")

    if args.output:
        print(f"\nResults saved to {args.output}")

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    raise SystemExit(exit_code)
