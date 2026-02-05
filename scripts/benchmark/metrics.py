"""Metrics collector for LLM benchmark infrastructure.

This module provides metrics collection for:
- Latency: P50, P95, P99, time-to-first-token
- VRAM: Peak usage, steady-state via nvidia-smi polling
- Throughput: Requests/min, tokens/sec from sustained load tests
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any

import httpx
import numpy as np


@dataclass
class LatencyMetrics:
    """Latency metrics for LLM inference.

    Attributes:
        p50: 50th percentile latency in seconds
        p95: 95th percentile latency in seconds
        p99: 99th percentile latency in seconds
        time_to_first_token: Time to first token in seconds
        mean: Mean latency in seconds
        count: Number of requests measured
    """

    p50: float
    p95: float
    p99: float
    time_to_first_token: float
    mean: float
    count: int


@dataclass
class VRAMMetrics:
    """VRAM metrics from GPU monitoring.

    Attributes:
        peak_usage_mb: Peak VRAM usage in MB
        steady_state_mb: Steady-state VRAM usage in MB
        min_usage_mb: Minimum VRAM usage in MB
        samples: Number of samples collected
    """

    peak_usage_mb: float
    steady_state_mb: float
    min_usage_mb: float
    samples: int


@dataclass
class ThroughputMetrics:
    """Throughput metrics for sustained load.

    Attributes:
        requests_per_min: Requests per minute
        tokens_per_sec: Tokens per second
        total_requests: Total requests processed
        total_tokens: Total tokens generated
        duration_sec: Test duration in seconds
    """

    requests_per_min: float
    tokens_per_sec: float
    total_requests: int
    total_tokens: int
    duration_sec: float


class ServiceUnavailableError(Exception):
    """Raised when the LLM service is not reachable."""

    pass


class GPUNotAvailableError(Exception):
    """Raised when GPU/nvidia-smi is not available."""

    pass


class MetricsCollector:
    """Collects performance metrics for LLM benchmarking.

    This class provides methods to:
    - Track request latencies and compute percentiles
    - Monitor VRAM usage via nvidia-smi polling
    - Calculate throughput metrics from sustained load tests
    """

    def __init__(self, service_url: str):
        """Initialize metrics collector.

        Args:
            service_url: URL of the LLM service to benchmark
        """
        self.service_url = service_url
        self._latencies: list[float] = []
        self._ttft_values: list[float] = []

    async def record_request(self, prompt: str) -> dict[str, Any]:
        """Record a single request and its metrics.

        Args:
            prompt: The prompt to send to the LLM service

        Returns:
            Response from the LLM service with timing metadata

        Raises:
            ServiceUnavailableError: If the service is not reachable
            TimeoutError: If the request times out
        """
        try:
            async with httpx.AsyncClient() as client:
                start_time = time.perf_counter()
                response = await client.post(
                    self.service_url,
                    json={"prompt": prompt},
                )
                elapsed_ms = (time.perf_counter() - start_time) * 1000

                # Check for HTTP errors
                response.raise_for_status()

                # Parse response JSON
                try:
                    data = response.json()
                except ValueError as e:
                    raise ServiceUnavailableError(f"Malformed JSON response: {e}") from e

                # Extract timing data, using fallbacks if not present
                total_time_ms = data.get("total_time_ms", elapsed_ms)
                ttft_ms = data.get("time_to_first_token_ms", total_time_ms * 0.3)

                # Track latency internally
                self._latencies.append(total_time_ms)
                self._ttft_values.append(ttft_ms)

                # Ensure response has timing fields
                result = dict(data)
                if "total_time_ms" not in result:
                    result["total_time_ms"] = total_time_ms
                if "time_to_first_token_ms" not in result:
                    result["time_to_first_token_ms"] = ttft_ms

                return result

        except httpx.ConnectError as e:
            raise ServiceUnavailableError(f"Connection error: {e}") from e
        except httpx.TimeoutException as e:
            raise TimeoutError(f"Request timed out: {e}") from e
        except httpx.HTTPStatusError as e:
            raise ServiceUnavailableError(f"HTTP error: {e}") from e

    def get_latency_metrics(self) -> LatencyMetrics:
        """Calculate latency percentiles from recorded requests.

        Returns:
            LatencyMetrics with P50, P95, P99, and TTFT

        Raises:
            ValueError: If no requests have been recorded
        """
        if not self._latencies:
            raise ValueError("No requests have been recorded")

        latencies = np.array(self._latencies)
        ttft_values = np.array(self._ttft_values)

        return LatencyMetrics(
            p50=float(np.percentile(latencies, 50)),
            p95=float(np.percentile(latencies, 95)),
            p99=float(np.percentile(latencies, 99)),
            time_to_first_token=float(np.mean(ttft_values)),
            mean=float(np.mean(latencies)),
            count=len(self._latencies),
        )

    async def monitor_vram(
        self, duration_sec: float = 10.0, interval_sec: float = 0.5
    ) -> VRAMMetrics:
        """Monitor VRAM usage via nvidia-smi polling.

        Args:
            duration_sec: How long to monitor in seconds
            interval_sec: Polling interval in seconds

        Returns:
            VRAMMetrics with peak, steady-state, and min usage

        Raises:
            GPUNotAvailableError: If nvidia-smi is not available
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
                stdout, stderr = await process.communicate()

                if process.returncode != 0:
                    raise GPUNotAvailableError(f"nvidia-smi failed: {stderr.decode().strip()}")

                # Parse output - handle multiple GPUs or single value
                output = stdout.decode().strip()
                for line in output.split("\n"):
                    stripped_line = line.strip()
                    if stripped_line:
                        # Handle "1024 MiB" or just "1024" format
                        value_str = stripped_line.replace("MiB", "").strip()
                        try:
                            vram_samples.append(float(value_str))
                        except ValueError:
                            continue

            except FileNotFoundError as e:
                raise GPUNotAvailableError(f"nvidia-smi not found: {e}") from e
            except OSError as e:
                raise GPUNotAvailableError(f"Failed to run nvidia-smi: {e}") from e

            await asyncio.sleep(interval_sec)

        if not vram_samples:
            raise GPUNotAvailableError("No VRAM samples collected")

        samples_array = np.array(vram_samples)

        return VRAMMetrics(
            peak_usage_mb=float(np.max(samples_array)),
            steady_state_mb=float(np.median(samples_array)),
            min_usage_mb=float(np.min(samples_array)),
            samples=len(vram_samples),
        )

    async def run_sustained_load(
        self,
        prompts: list[str],
        duration_sec: float = 60.0,
        concurrent_requests: int = 1,
    ) -> ThroughputMetrics:
        """Run sustained load test to measure throughput.

        Args:
            prompts: List of prompts to cycle through
            duration_sec: How long to run the test in seconds
            concurrent_requests: Number of concurrent requests

        Returns:
            ThroughputMetrics with requests/min and tokens/sec

        Raises:
            ValueError: If prompts list is empty
            ServiceUnavailableError: If the service becomes unavailable
        """
        if not prompts:
            raise ValueError("Prompts list cannot be empty")

        total_requests = 0
        total_tokens = 0
        prompt_index = 0
        start_time = time.perf_counter()

        async def worker() -> tuple[int, int]:
            """Worker coroutine that sends requests until duration expires."""
            nonlocal prompt_index
            worker_requests = 0
            worker_tokens = 0

            while (time.perf_counter() - start_time) < duration_sec:
                # Cycle through prompts
                prompt = prompts[prompt_index % len(prompts)]
                prompt_index += 1

                result = await self.record_request(prompt)
                worker_requests += 1
                worker_tokens += result.get("tokens", 0)

            return worker_requests, worker_tokens

        # Run concurrent workers
        tasks = [asyncio.create_task(worker()) for _ in range(concurrent_requests)]
        results = await asyncio.gather(*tasks)

        for req_count, token_count in results:
            total_requests += req_count
            total_tokens += token_count

        actual_duration = time.perf_counter() - start_time
        requests_per_min = (total_requests / actual_duration) * 60
        tokens_per_sec = total_tokens / actual_duration

        return ThroughputMetrics(
            requests_per_min=requests_per_min,
            tokens_per_sec=tokens_per_sec,
            total_requests=total_requests,
            total_tokens=total_tokens,
            duration_sec=actual_duration,
        )
