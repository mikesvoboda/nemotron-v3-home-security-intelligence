"""Metrics collector for LLM benchmark infrastructure.

This module provides metrics collection for:
- Latency: P50, P95, P99, time-to-first-token
- VRAM: Peak usage, steady-state via nvidia-smi polling
- Throughput: Requests/min, tokens/sec from sustained load tests
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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
        raise NotImplementedError("MetricsCollector.__init__ not implemented")

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
        raise NotImplementedError("MetricsCollector.record_request not implemented")

    def get_latency_metrics(self) -> LatencyMetrics:
        """Calculate latency percentiles from recorded requests.

        Returns:
            LatencyMetrics with P50, P95, P99, and TTFT

        Raises:
            ValueError: If no requests have been recorded
        """
        raise NotImplementedError("MetricsCollector.get_latency_metrics not implemented")

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
        raise NotImplementedError("MetricsCollector.monitor_vram not implemented")

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
        raise NotImplementedError("MetricsCollector.run_sustained_load not implemented")


class ServiceUnavailableError(Exception):
    """Raised when the LLM service is not reachable."""

    pass


class GPUNotAvailableError(Exception):
    """Raised when GPU/nvidia-smi is not available."""

    pass
