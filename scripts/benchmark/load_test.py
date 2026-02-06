#!/usr/bin/env python3
"""Load testing module for batching and scheduling optimization benchmarks.

Phase 5: Batching and Scheduling Optimization

This module provides sustained load and burst testing capabilities:
- Sustained load: Steady stream of requests over time with configurable ramp-up
- Burst testing: Sudden spikes to measure queue behavior and batching efficiency
- Measures throughput improvements from batching/priority queue optimizations

Usage:
    python scripts/benchmark/load_test.py \
        --mode sustained \
        --duration 60 \
        --rps 5 \
        --url http://localhost:8000/api/enrichment

    python scripts/benchmark/load_test.py \
        --mode burst \
        --burst-size 10 \
        --burst-interval 5 \
        --total-bursts 6 \
        --url http://localhost:8000/api/enrichment
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import numpy as np


@dataclass
class LoadConfig:
    """Base configuration for load testing.

    Attributes:
        target_url: URL of the service to test
        duration_seconds: Duration of the load test in seconds
        requests_per_second: Target request rate (RPS)
        timeout_seconds: Request timeout in seconds
    """

    target_url: str
    duration_seconds: int = 60
    requests_per_second: float = 5.0
    timeout_seconds: float = 30.0


@dataclass
class SustainedLoadConfig(LoadConfig):
    """Configuration for sustained load testing with ramp-up support.

    Extends LoadConfig with:
        ramp_up_seconds: Duration of ramp-up period (0 = no ramp)
        steady_state_start: Time when steady-state metrics begin
        measure_priority_latency: Whether to track latency by priority
        measure_coalescing: Whether to track batch coalescing metrics
        evaluation_set_path: Optional path to evaluation set directory
    """

    ramp_up_seconds: int = 0
    steady_state_start: int = 0
    measure_priority_latency: bool = False
    measure_coalescing: bool = False
    evaluation_set_path: Path | None = None


@dataclass
class BurstConfig:
    """Configuration for burst/spike load testing.

    Attributes:
        target_url: URL of the service to test
        burst_size: Number of concurrent requests per burst
        burst_interval_seconds: Time between bursts
        total_bursts: Total number of bursts to send
    """

    target_url: str
    burst_size: int = 10
    burst_interval_seconds: float = 5.0
    total_bursts: int = 6

    @property
    def total_requests(self) -> int:
        """Calculate total requests from burst parameters."""
        return self.burst_size * self.total_bursts


@dataclass
class LoadTestMetrics:
    """Results from load test execution.

    Attributes:
        total_requests: Total number of requests sent
        successful_requests: Number of successful (2xx) responses
        failed_requests: Number of failed requests
        latency_p50_ms: 50th percentile latency in milliseconds
        latency_p95_ms: 95th percentile latency in milliseconds
        latency_p99_ms: 99th percentile latency in milliseconds
        throughput_rps: Actual requests per second achieved
        test_duration_seconds: Total test duration in seconds
        error_breakdown: Count of errors by type (timeout, 5xx, connection_error)
        latency_by_priority: Latency metrics grouped by priority level
        batches_coalesced: Number of batches that were coalesced
    """

    total_requests: int
    successful_requests: int
    failed_requests: int
    latency_p50_ms: float
    latency_p95_ms: float
    latency_p99_ms: float
    throughput_rps: float
    test_duration_seconds: float
    error_breakdown: dict[str, int] = field(default_factory=dict)
    latency_by_priority: dict[str, dict[str, float]] = field(default_factory=dict)
    batches_coalesced: int = 0

    @property
    def success_rate(self) -> float:
        """Calculate success rate as a fraction (0.0 to 1.0)."""
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests


# Object labels for detection payload generation - affects priority
OBJECT_LABELS = [
    "person",
    "car",
    "dog",
    "cat",
    "package",
    "bicycle",
    "bird",
    "unknown",
]

# Priority mapping based on object type
PRIORITY_MAP = {
    "person": "high",
    "package": "high",
    "car": "medium",
    "bicycle": "medium",
    "dog": "low",
    "cat": "low",
    "bird": "low",
    "unknown": "low",
}


class LoadTestRunner:
    """Executes load tests against a target service.

    This class handles:
    - Sustained load testing with configurable ramp-up
    - Burst/spike testing for queue behavior analysis
    - Payload generation for realistic detection scenarios
    - Metrics collection and aggregation
    """

    def __init__(self, config: LoadConfig | SustainedLoadConfig | BurstConfig) -> None:
        """Initialize the load test runner.

        Args:
            config: Configuration for the load test
        """
        self.config = config
        self._latencies: list[float] = []
        self._errors: dict[str, int] = {}
        self._priority_latencies: dict[str, list[float]] = {}
        self._batches_coalesced: int = 0
        self._evaluation_payloads: list[dict[str, Any]] = []

        # Load evaluation set if path provided
        if isinstance(config, SustainedLoadConfig) and config.evaluation_set_path:
            self._load_evaluation_set(config.evaluation_set_path)

    def _load_evaluation_set(self, path: Path) -> None:
        """Load evaluation set payloads from disk.

        Args:
            path: Path to evaluation set directory
        """
        if not path.exists():
            return

        # Load individual event files
        json_files = sorted(path.glob("evt_*.json"))
        for json_file in json_files:
            try:
                event_data = json.loads(json_file.read_text())
                self._evaluation_payloads.append(event_data)
            except (json.JSONDecodeError, OSError):
                continue

    def generate_detection_payload(self) -> dict[str, Any]:
        """Generate a realistic detection payload for testing.

        Returns:
            Dictionary containing camera_id and detections list
        """
        # Using standard random for benchmark payloads - not security-sensitive
        num_detections = random.randint(1, 5)  # noqa: S311
        detections = []

        for _ in range(num_detections):
            label = random.choice(OBJECT_LABELS)  # noqa: S311
            detection = {
                "label": label,
                "confidence": round(random.uniform(0.7, 0.99), 2),  # noqa: S311
                "bbox": [
                    random.randint(0, 1000),  # noqa: S311
                    random.randint(0, 1000),  # noqa: S311
                    random.randint(100, 500),  # noqa: S311
                    random.randint(100, 500),  # noqa: S311
                ],
                "priority": PRIORITY_MAP.get(label, "low"),
            }
            detections.append(detection)

        return {
            "camera_id": f"cam_{random.randint(1, 10)}",  # noqa: S311
            "timestamp": time.time(),
            "detections": detections,
        }

    def _calculate_rate_at_time(self, elapsed_time: float) -> float:
        """Calculate the request rate at a given time during ramp-up.

        Args:
            elapsed_time: Time elapsed since test start in seconds

        Returns:
            Target requests per second at this time
        """
        if not isinstance(self.config, SustainedLoadConfig):
            # LoadConfig has requests_per_second, BurstConfig doesn't have this method called
            if hasattr(self.config, "requests_per_second"):
                return self.config.requests_per_second
            return 1.0  # Default fallback

        ramp_up = self.config.ramp_up_seconds
        target_rps = self.config.requests_per_second

        if ramp_up <= 0 or elapsed_time >= ramp_up:
            return target_rps

        # Linear ramp-up from 0 to target
        progress = elapsed_time / ramp_up
        return target_rps * progress

    async def run_sustained(self) -> LoadTestMetrics:
        """Run a sustained load test.

        Sends requests at a steady rate (with optional ramp-up) for the
        configured duration.

        Returns:
            LoadTestMetrics containing test results
        """
        if not isinstance(self.config, LoadConfig | SustainedLoadConfig):
            raise TypeError("Config must be LoadConfig or SustainedLoadConfig")

        # Handle zero duration edge case
        if self.config.duration_seconds <= 0:
            return LoadTestMetrics(
                total_requests=0,
                successful_requests=0,
                failed_requests=0,
                latency_p50_ms=0.0,
                latency_p95_ms=0.0,
                latency_p99_ms=0.0,
                throughput_rps=0.0,
                test_duration_seconds=0.0,
                error_breakdown={},
                latency_by_priority={},
                batches_coalesced=0,
            )

        self._latencies = []
        self._errors = {}
        self._priority_latencies = {}
        self._batches_coalesced = 0

        start_time = time.monotonic()
        end_time = start_time + self.config.duration_seconds
        total_requests = 0
        successful_requests = 0

        measure_priority = (
            isinstance(self.config, SustainedLoadConfig) and self.config.measure_priority_latency
        )
        measure_coalescing = (
            isinstance(self.config, SustainedLoadConfig) and self.config.measure_coalescing
        )

        timeout = httpx.Timeout(self.config.timeout_seconds)

        async with httpx.AsyncClient(timeout=timeout) as client:
            while time.monotonic() < end_time:
                elapsed = time.monotonic() - start_time
                current_rate = self._calculate_rate_at_time(elapsed)

                if current_rate <= 0:
                    await asyncio.sleep(0.1)
                    continue

                # Calculate delay for next request
                delay = 1.0 / current_rate

                payload = self.generate_detection_payload()
                priority = payload["detections"][0].get("priority", "low")

                request_start = time.monotonic()
                try:
                    response = await client.post(self.config.target_url, json=payload)
                    latency_ms = (time.monotonic() - request_start) * 1000
                    self._latencies.append(latency_ms)

                    if measure_priority:
                        if priority not in self._priority_latencies:
                            self._priority_latencies[priority] = []
                        self._priority_latencies[priority].append(latency_ms)

                    if measure_coalescing:
                        # Check response for coalescing info
                        try:
                            resp_data = response.json()
                            if resp_data.get("coalesced", False):
                                self._batches_coalesced += 1
                        except (json.JSONDecodeError, ValueError):
                            pass

                    total_requests += 1
                    if response.status_code < 400:
                        successful_requests += 1
                    elif response.status_code >= 500:
                        self._errors["5xx"] = self._errors.get("5xx", 0) + 1

                except httpx.TimeoutException:
                    total_requests += 1
                    self._errors["timeout"] = self._errors.get("timeout", 0) + 1
                except (httpx.ConnectError, ConnectionError):
                    total_requests += 1
                    self._errors["connection_error"] = self._errors.get("connection_error", 0) + 1
                except Exception:
                    total_requests += 1
                    self._errors["other"] = self._errors.get("other", 0) + 1

                # Wait for next request
                await asyncio.sleep(max(0, delay - (time.monotonic() - request_start)))

        test_duration = time.monotonic() - start_time
        failed_requests = total_requests - successful_requests

        # Calculate latency percentiles
        if self._latencies:
            latencies_array = np.array(self._latencies)
            p50 = float(np.percentile(latencies_array, 50))
            p95 = float(np.percentile(latencies_array, 95))
            p99 = float(np.percentile(latencies_array, 99))
        else:
            p50 = p95 = p99 = 0.0

        # Calculate throughput
        throughput = total_requests / test_duration if test_duration > 0 else 0.0

        # Build priority latency metrics
        latency_by_priority = {}
        if measure_priority:
            for prio, latencies in self._priority_latencies.items():
                if latencies:
                    arr = np.array(latencies)
                    latency_by_priority[prio] = {
                        "p50": float(np.percentile(arr, 50)),
                        "p95": float(np.percentile(arr, 95)),
                        "p99": float(np.percentile(arr, 99)),
                        "count": len(latencies),
                    }

        return LoadTestMetrics(
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            latency_p50_ms=p50,
            latency_p95_ms=p95,
            latency_p99_ms=p99,
            throughput_rps=throughput,
            test_duration_seconds=test_duration,
            error_breakdown=self._errors,
            latency_by_priority=latency_by_priority,
            batches_coalesced=self._batches_coalesced,
        )

    async def run_burst(self) -> LoadTestMetrics:
        """Run a burst/spike load test.

        Sends bursts of concurrent requests with intervals between bursts
        to test queue behavior and batching.

        Returns:
            LoadTestMetrics containing test results
        """
        if not isinstance(self.config, BurstConfig):
            raise TypeError("Config must be BurstConfig for burst tests")

        self._latencies = []
        self._errors = {}

        start_time = time.monotonic()
        total_requests = 0
        successful_requests = 0

        timeout = httpx.Timeout(30.0)

        async with httpx.AsyncClient(timeout=timeout) as client:
            for burst_num in range(self.config.total_bursts):
                # Create tasks for all requests in this burst
                tasks = []
                for _ in range(self.config.burst_size):
                    payload = self.generate_detection_payload()
                    tasks.append(self._send_request(client, payload))

                # Send all requests in burst concurrently
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for result in results:
                    total_requests += 1
                    if isinstance(result, BaseException):
                        if isinstance(result, httpx.TimeoutException):
                            self._errors["timeout"] = self._errors.get("timeout", 0) + 1
                        elif isinstance(result, httpx.ConnectError | ConnectionError):
                            self._errors["connection_error"] = (
                                self._errors.get("connection_error", 0) + 1
                            )
                        else:
                            self._errors["other"] = self._errors.get("other", 0) + 1
                    elif isinstance(result, tuple):
                        latency_ms, status_code = result
                        self._latencies.append(latency_ms)
                        if status_code < 400:
                            successful_requests += 1
                        elif status_code >= 500:
                            self._errors["5xx"] = self._errors.get("5xx", 0) + 1

                # Wait for interval before next burst (except after last burst)
                if burst_num < self.config.total_bursts - 1:
                    await asyncio.sleep(self.config.burst_interval_seconds)

        test_duration = time.monotonic() - start_time
        failed_requests = total_requests - successful_requests

        # Calculate latency percentiles
        if self._latencies:
            latencies_array = np.array(self._latencies)
            p50 = float(np.percentile(latencies_array, 50))
            p95 = float(np.percentile(latencies_array, 95))
            p99 = float(np.percentile(latencies_array, 99))
        else:
            p50 = p95 = p99 = 0.0

        # Calculate throughput
        throughput = total_requests / test_duration if test_duration > 0 else 0.0

        return LoadTestMetrics(
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            latency_p50_ms=p50,
            latency_p95_ms=p95,
            latency_p99_ms=p99,
            throughput_rps=throughput,
            test_duration_seconds=test_duration,
            error_breakdown=self._errors,
        )

    async def _send_request(
        self, client: httpx.AsyncClient, payload: dict[str, Any]
    ) -> tuple[float, int]:
        """Send a single request and measure latency.

        Args:
            client: httpx async client
            payload: Request payload

        Returns:
            Tuple of (latency_ms, status_code)

        Raises:
            Exception if request fails
        """
        request_start = time.monotonic()
        response = await client.post(self.config.target_url, json=payload)
        latency_ms = (time.monotonic() - request_start) * 1000
        return latency_ms, response.status_code


def generate_report(metrics: LoadTestMetrics) -> dict[str, Any]:
    """Generate a structured report from load test metrics.

    Args:
        metrics: LoadTestMetrics from a completed test

    Returns:
        Dictionary with summary, latency, and throughput sections
    """
    return {
        "summary": {
            "total_requests": metrics.total_requests,
            "successful_requests": metrics.successful_requests,
            "failed_requests": metrics.failed_requests,
            "success_rate": metrics.success_rate,
            "test_duration_seconds": metrics.test_duration_seconds,
            "error_breakdown": metrics.error_breakdown,
        },
        "latency": {
            "p50_ms": metrics.latency_p50_ms,
            "p95_ms": metrics.latency_p95_ms,
            "p99_ms": metrics.latency_p99_ms,
        },
        "throughput": {
            "requests_per_second": metrics.throughput_rps,
        },
    }


def save_report(metrics: LoadTestMetrics, path: Path) -> None:
    """Save load test report to a JSON file.

    Args:
        metrics: LoadTestMetrics from a completed test
        path: Path to save the JSON report
    """
    report = generate_report(metrics)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2))


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        args: Command-line arguments (None = use sys.argv)

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="Load testing for batching and scheduling optimization",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--mode",
        type=str,
        choices=["sustained", "burst"],
        default="sustained",
        help="Test mode: sustained load or burst testing",
    )

    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Duration for sustained load test in seconds",
    )

    parser.add_argument(
        "--rps",
        type=float,
        default=5.0,
        help="Target requests per second for sustained load",
    )

    parser.add_argument(
        "--url",
        type=str,
        default="http://localhost:8000/api/enrichment",
        help="Target URL for load testing",
    )

    parser.add_argument(
        "--burst-size",
        type=int,
        default=10,
        help="Number of concurrent requests per burst",
    )

    parser.add_argument(
        "--burst-interval",
        type=float,
        default=5.0,
        help="Interval between bursts in seconds",
    )

    parser.add_argument(
        "--total-bursts",
        type=int,
        default=6,
        help="Total number of bursts to send",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/load_test_results.json"),
        help="Path to save results JSON",
    )

    parser.add_argument(
        "--ramp-up",
        type=int,
        default=0,
        help="Ramp-up period in seconds (sustained mode only)",
    )

    parser.add_argument(
        "--measure-priority",
        action="store_true",
        help="Measure latency by priority level",
    )

    parser.add_argument(
        "--measure-coalescing",
        action="store_true",
        help="Track batch coalescing metrics",
    )

    return parser.parse_args(args if args is not None else [])


async def main() -> int:
    """Main entry point for load testing.

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    args = parse_args()

    if args.mode == "sustained":
        sustained_config = SustainedLoadConfig(
            target_url=args.url,
            duration_seconds=args.duration,
            requests_per_second=args.rps,
            ramp_up_seconds=args.ramp_up,
            measure_priority_latency=args.measure_priority,
            measure_coalescing=args.measure_coalescing,
        )
        runner = LoadTestRunner(sustained_config)
        print(f"Running sustained load test at {args.rps} RPS for {args.duration}s...")
        metrics = await runner.run_sustained()
    else:
        burst_config = BurstConfig(
            target_url=args.url,
            burst_size=args.burst_size,
            burst_interval_seconds=args.burst_interval,
            total_bursts=args.total_bursts,
        )
        runner = LoadTestRunner(burst_config)
        print(f"Running burst test: {args.burst_size} requests x {args.total_bursts} bursts...")
        metrics = await runner.run_burst()

    # Save and display results
    save_report(metrics, args.output)
    print(f"\nResults saved to {args.output}")

    report = generate_report(metrics)
    print("\n--- Summary ---")
    print(f"Total requests: {report['summary']['total_requests']}")
    print(f"Success rate: {report['summary']['success_rate']:.2%}")
    print(f"P50 latency: {report['latency']['p50_ms']:.2f}ms")
    print(f"P95 latency: {report['latency']['p95_ms']:.2f}ms")
    print(f"P99 latency: {report['latency']['p99_ms']:.2f}ms")
    print(f"Throughput: {report['throughput']['requests_per_second']:.2f} RPS")

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    raise SystemExit(exit_code)
