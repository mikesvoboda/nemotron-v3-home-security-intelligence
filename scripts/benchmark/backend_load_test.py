#!/usr/bin/env python3
"""Backend load test for Phase 5 batch processing optimizations.

This module exercises the backend's batch processing pipeline to measure:
- Batch coalescing efficiency (multiple detections merged into single LLM calls)
- Priority scheduling (high-priority detections processed first)
- End-to-end latency by priority level

The test submits synthetic detections through the batch aggregator's internal
mechanisms and measures the resulting batch processing metrics.

Usage:
    python scripts/benchmark/backend_load_test.py \
        --duration 60 \
        --rps 5 \
        --api-url http://localhost:8000

    python scripts/benchmark/backend_load_test.py \
        --mode burst \
        --burst-size 20 \
        --total-bursts 5 \
        --api-url http://localhost:8000

Phase 5 Optimization Targets:
    - 20-40% reduction in inference calls through coalescing
    - P0 (critical) latency < P3 (low) latency
    - Weapons/fire detected immediately (bypass batching)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import numpy as np


# Priority levels matching backend/services/batch_coalescer.py
class Priority:
    """Priority levels for detection processing."""

    P0_CRITICAL = 4  # Weapons, fire, unknown persons at night
    P1_HIGH = 3  # Unknown vehicles
    P2_NORMAL = 2  # Regular daytime detections
    P3_LOW = 1  # Known faces, household members

    @classmethod
    def name(cls, value: int) -> str:
        """Get priority name from value."""
        names = {4: "P0_CRITICAL", 3: "P1_HIGH", 2: "P2_NORMAL", 1: "P3_LOW"}
        return names.get(value, "UNKNOWN")


# Detection types categorized by priority
CRITICAL_OBJECTS = ["gun", "knife", "fire", "smoke", "intruder"]
HIGH_OBJECTS = ["car", "truck", "van", "motorcycle"]
NORMAL_OBJECTS = ["person", "bicycle", "package"]
LOW_OBJECTS = ["dog", "cat", "bird", "squirrel"]

# All object types for random selection with weighted distribution
# Weight distribution: ~5% critical, ~20% high, ~50% normal, ~25% low
OBJECT_WEIGHTS = {
    "gun": 2,
    "knife": 2,
    "fire": 0.5,
    "smoke": 0.5,
    "car": 10,
    "truck": 5,
    "van": 3,
    "motorcycle": 2,
    "person": 35,
    "bicycle": 5,
    "package": 10,
    "dog": 10,
    "cat": 10,
    "bird": 5,
}


def get_priority_for_object(object_type: str) -> int:
    """Get priority level for an object type."""
    object_lower = object_type.lower()
    if object_lower in [o.lower() for o in CRITICAL_OBJECTS]:
        return Priority.P0_CRITICAL
    if object_lower in [o.lower() for o in HIGH_OBJECTS]:
        return Priority.P1_HIGH
    if object_lower in [o.lower() for o in LOW_OBJECTS]:
        return Priority.P3_LOW
    return Priority.P2_NORMAL


def weighted_random_object() -> str:
    """Select random object type with weighted probability.

    Note: Uses standard random for benchmark payloads - not security-sensitive.
    """
    objects = list(OBJECT_WEIGHTS.keys())
    weights = list(OBJECT_WEIGHTS.values())
    total = sum(weights)
    weights = [w / total for w in weights]
    return random.choices(objects, weights=weights, k=1)[0]  # noqa: S311


@dataclass
class DetectionPayload:
    """Represents a synthetic detection for testing."""

    detection_id: int
    camera_id: str
    object_type: str
    confidence: float
    bbox: list[int]
    timestamp: float
    priority: int

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API submission."""
        return {
            "detection_id": self.detection_id,
            "camera_id": self.camera_id,
            "object_type": self.object_type,
            "confidence": self.confidence,
            "bbox": self.bbox,
            "timestamp": self.timestamp,
            "priority": self.priority,
        }


@dataclass
class BatchMetrics:
    """Metrics for batch processing analysis."""

    # Latency by priority level (ms)
    latencies_by_priority: dict[int, list[float]] = field(default_factory=lambda: defaultdict(list))

    # Coalescing metrics
    total_detections_submitted: int = 0
    total_batches_created: int = 0
    total_llm_calls: int = 0
    detections_coalesced: int = 0

    # Throughput
    start_time: float = 0.0
    end_time: float = 0.0

    # Error tracking
    errors: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    @property
    def coalescing_ratio(self) -> float:
        """Calculate ratio of LLM calls to detections (lower is better)."""
        if self.total_detections_submitted == 0:
            return 0.0
        return self.total_llm_calls / self.total_detections_submitted

    @property
    def inference_reduction_pct(self) -> float:
        """Calculate percentage reduction in inference calls."""
        if self.total_detections_submitted == 0:
            return 0.0
        # Without coalescing, each detection = 1 LLM call
        expected_calls = self.total_detections_submitted
        actual_calls = self.total_llm_calls
        reduction = (expected_calls - actual_calls) / expected_calls * 100
        return max(0.0, reduction)

    @property
    def throughput_events_per_min(self) -> float:
        """Calculate events processed per minute."""
        duration = self.end_time - self.start_time
        if duration == 0:
            return 0.0
        return (self.total_detections_submitted / duration) * 60

    def get_latency_stats(self, priority: int) -> dict[str, float]:
        """Get latency statistics for a priority level."""
        latencies = self.latencies_by_priority.get(priority, [])
        if not latencies:
            return {"p50": 0.0, "p95": 0.0, "p99": 0.0, "mean": 0.0, "count": 0}
        arr = np.array(latencies)
        return {
            "p50": float(np.percentile(arr, 50)),
            "p95": float(np.percentile(arr, 95)),
            "p99": float(np.percentile(arr, 99)),
            "mean": float(np.mean(arr)),
            "count": len(latencies),
        }


@dataclass
class LoadTestConfig:
    """Configuration for the load test."""

    api_url: str = "http://localhost:8000"
    duration_seconds: int = 60
    requests_per_second: float = 5.0
    mode: str = "sustained"  # "sustained" or "burst"
    burst_size: int = 20
    burst_interval: float = 5.0
    total_bursts: int = 5
    num_cameras: int = 4
    timeout_seconds: float = 120.0
    # Coalescing test parameters
    same_camera_pct: float = 0.6  # 60% of detections from same camera (tests coalescing)
    time_window_seconds: float = 5.0  # Time window for same-camera submissions


class BackendLoadTestRunner:
    """Runs load tests against the backend batch processing pipeline.

    This class:
    1. Generates synthetic detections with varied priorities
    2. Submits them to the backend via the seed/admin API
    3. Monitors batch processing metrics via metrics endpoint
    4. Measures latency, coalescing, and priority scheduling
    """

    def __init__(self, config: LoadTestConfig) -> None:
        """Initialize the load test runner.

        Args:
            config: Load test configuration
        """
        self.config = config
        self.metrics = BatchMetrics()
        self._detection_counter = 0
        self._camera_ids = [f"loadtest-cam-{i}" for i in range(config.num_cameras)]
        self._current_camera_idx = 0
        # Track submission times by detection_id for latency calculation
        self._submission_times: dict[int, tuple[float, int]] = {}  # id -> (time, priority)

    def _generate_detection(self, force_camera: str | None = None) -> DetectionPayload:
        """Generate a synthetic detection payload.

        Args:
            force_camera: Force specific camera ID (for coalescing tests)

        Returns:
            DetectionPayload ready for submission
        """
        self._detection_counter += 1

        # Select camera (biased toward same camera for coalescing tests)
        # Note: Using standard random for benchmark - not security-sensitive
        if force_camera:
            camera_id = force_camera
        elif random.random() < self.config.same_camera_pct:  # noqa: S311
            # Use current camera (enables coalescing)
            camera_id = self._camera_ids[self._current_camera_idx]
        else:
            # Random camera
            camera_id = random.choice(self._camera_ids)  # noqa: S311
            self._current_camera_idx = self._camera_ids.index(camera_id)

        # Select object type with weighted probability
        object_type = weighted_random_object()
        priority = get_priority_for_object(object_type)

        # Generate confidence (higher for critical objects)
        if priority == Priority.P0_CRITICAL:
            confidence = random.uniform(0.85, 0.99)  # noqa: S311
        elif priority == Priority.P1_HIGH:
            confidence = random.uniform(0.75, 0.95)  # noqa: S311
        else:
            confidence = random.uniform(0.65, 0.90)  # noqa: S311

        # Generate bounding box
        x = random.randint(0, 1000)  # noqa: S311
        y = random.randint(0, 800)  # noqa: S311
        w = random.randint(50, 300)  # noqa: S311
        h = random.randint(50, 400)  # noqa: S311

        return DetectionPayload(
            detection_id=self._detection_counter,
            camera_id=camera_id,
            object_type=object_type,
            confidence=round(confidence, 3),
            bbox=[x, y, w, h],
            timestamp=time.time(),
            priority=priority,
        )

    def _generate_coalescing_batch(self) -> list[DetectionPayload]:
        """Generate a batch of detections for coalescing tests.

        Creates multiple detections from the same camera with similar
        timestamps to test batch coalescing efficiency.

        Returns:
            List of DetectionPayload objects
        """
        # Select a single camera for this batch
        camera_id = self._camera_ids[self._current_camera_idx]
        self._current_camera_idx = (self._current_camera_idx + 1) % len(self._camera_ids)

        # Generate 3-8 detections from same camera
        num_detections = random.randint(3, 8)  # noqa: S311
        detections = []

        for _ in range(num_detections):
            detection = self._generate_detection(force_camera=camera_id)
            detections.append(detection)

        return detections

    async def _submit_detection_via_api(
        self,
        client: httpx.AsyncClient,
        detection: DetectionPayload,
    ) -> dict[str, Any] | None:
        """Submit a detection via the backend API.

        This uses the internal batch aggregator test endpoint or creates
        detection records and triggers analysis.

        Args:
            client: HTTP client
            detection: Detection payload

        Returns:
            Response data or None on failure
        """
        # Track submission time for latency calculation
        submit_time = time.time()
        self._submission_times[detection.detection_id] = (submit_time, detection.priority)
        self.metrics.total_detections_submitted += 1

        try:
            # Try the batch test endpoint (if available in debug mode)
            # This endpoint directly invokes the batch aggregator
            response = await client.post(
                f"{self.config.api_url}/api/debug/batch/add-detection",
                json={
                    "camera_id": detection.camera_id,
                    "detection_id": detection.detection_id,
                    "object_type": detection.object_type,
                    "confidence": detection.confidence,
                    "threat_type": (
                        detection.object_type if detection.object_type in CRITICAL_OBJECTS else None
                    ),
                },
                timeout=self.config.timeout_seconds,
            )

            if response.status_code == 200:
                data: dict[str, Any] = response.json()
                # Track if this triggered a batch
                if data.get("batch_id"):
                    self.metrics.total_batches_created += 1
                return data
            elif response.status_code == 404:
                # Endpoint not available, fall back to alternative approach
                return await self._submit_via_events_api(client, detection)
            else:
                self.metrics.errors[f"http_{response.status_code}"] += 1
                return None

        except httpx.TimeoutException:
            self.metrics.errors["timeout"] += 1
            return None
        except httpx.ConnectError:
            self.metrics.errors["connection_error"] += 1
            return None
        except Exception as e:
            self.metrics.errors["other"] += 1
            return None

    async def _submit_via_events_api(
        self,
        client: httpx.AsyncClient,
        detection: DetectionPayload,
    ) -> dict[str, Any] | None:
        """Submit detection via events/analyze endpoint.

        Creates a synthetic batch and triggers analysis.

        Args:
            client: HTTP client
            detection: Detection payload

        Returns:
            Response data or None on failure
        """
        try:
            # Create a synthetic batch ID
            batch_id = f"loadtest-{uuid.uuid4().hex[:8]}"

            # Try to trigger analysis via the streaming endpoint
            # This is the closest we can get to the batch pipeline without
            # direct access to the batch aggregator
            response = await client.get(
                f"{self.config.api_url}/api/events/analyze/{batch_id}/stream",
                params={
                    "camera_id": detection.camera_id,
                    "detection_ids": str(detection.detection_id),
                },
                timeout=self.config.timeout_seconds,
            )

            if response.status_code == 200:
                # Parse SSE response
                return {"batch_id": batch_id, "status": "submitted"}
            else:
                self.metrics.errors[f"http_{response.status_code}"] += 1
                return None

        except Exception:
            self.metrics.errors["api_fallback_error"] += 1
            return None

    async def _fetch_batch_metrics(self, client: httpx.AsyncClient) -> dict[str, Any] | None:
        """Fetch batch processing metrics from the backend.

        Args:
            client: HTTP client

        Returns:
            Metrics data or None on failure
        """
        try:
            response = await client.get(
                f"{self.config.api_url}/api/debug/batch/metrics",
                timeout=10.0,
            )
            if response.status_code == 200:
                result: dict[str, Any] = response.json()
                return result
        except Exception:
            # Silently ignore metric fetch failures - non-critical for load test
            return None
        return None

    async def _fetch_coalescer_metrics(self, client: httpx.AsyncClient) -> dict[str, Any] | None:
        """Fetch coalescer-specific metrics.

        Args:
            client: HTTP client

        Returns:
            Coalescer metrics or None on failure
        """
        try:
            # Try Prometheus metrics endpoint
            response = await client.get(
                f"{self.config.api_url}/metrics",
                timeout=10.0,
            )
            if response.status_code == 200:
                # Parse Prometheus format for coalescing metrics
                text = response.text
                metrics = {}

                for line in text.split("\n"):
                    if line.startswith("batch_coalesce_"):
                        parts = line.split(" ")
                        if len(parts) >= 2:
                            name = parts[0].split("{")[0]
                            try:
                                value = float(parts[-1])
                                metrics[name] = value
                            except ValueError:
                                pass

                return metrics
        except Exception:
            # Silently ignore metric fetch failures - non-critical for load test
            return None
        return None

    async def run_sustained_load(self) -> BatchMetrics:
        """Run sustained load test.

        Submits detections at a steady rate for the configured duration.

        Returns:
            BatchMetrics with test results
        """
        self.metrics = BatchMetrics()
        self.metrics.start_time = time.time()

        end_time = self.metrics.start_time + self.config.duration_seconds
        interval = 1.0 / self.config.requests_per_second

        timeout = httpx.Timeout(self.config.timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            # Initial metrics fetch
            initial_metrics = await self._fetch_coalescer_metrics(client)

            while time.time() < end_time:
                request_start = time.time()

                # Generate and submit detection
                detection = self._generate_detection()
                await self._submit_detection_via_api(client, detection)

                # Record latency by priority
                latency_ms = (time.time() - request_start) * 1000
                self.metrics.latencies_by_priority[detection.priority].append(latency_ms)

                # Wait for next interval
                elapsed = time.time() - request_start
                sleep_time = max(0, interval - elapsed)
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

            # Final metrics fetch
            final_metrics = await self._fetch_coalescer_metrics(client)

            # Calculate coalescing metrics from Prometheus data
            if initial_metrics and final_metrics:
                initial_merges = initial_metrics.get("batch_coalesce_merges_total", 0)
                final_merges = final_metrics.get("batch_coalesce_merges_total", 0)
                self.metrics.detections_coalesced = int(final_merges - initial_merges)

                initial_calls = initial_metrics.get("batch_llm_calls_total", 0)
                final_calls = final_metrics.get("batch_llm_calls_total", 0)
                self.metrics.total_llm_calls = int(final_calls - initial_calls)

        self.metrics.end_time = time.time()
        return self.metrics

    async def run_burst_load(self) -> BatchMetrics:
        """Run burst load test.

        Sends bursts of concurrent detections to test coalescing under load.

        Returns:
            BatchMetrics with test results
        """
        self.metrics = BatchMetrics()
        self.metrics.start_time = time.time()

        timeout = httpx.Timeout(self.config.timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            # Initial metrics fetch
            initial_metrics = await self._fetch_coalescer_metrics(client)

            for burst_num in range(self.config.total_bursts):
                # Generate burst of detections (some from same camera for coalescing)
                detections = []

                # Half from same camera (coalescing test)
                coalesce_batch = self._generate_coalescing_batch()
                detections.extend(coalesce_batch)

                # Half random cameras
                for _ in range(self.config.burst_size // 2):
                    detections.append(self._generate_detection())

                # Submit all concurrently
                tasks = []
                for detection in detections:
                    task = self._submit_detection_via_api(client, detection)
                    tasks.append(task)

                start = time.time()
                await asyncio.gather(*tasks, return_exceptions=True)
                burst_latency = (time.time() - start) * 1000

                # Record latencies
                for detection in detections:
                    self.metrics.latencies_by_priority[detection.priority].append(
                        burst_latency / len(detections)
                    )

                # Wait between bursts
                if burst_num < self.config.total_bursts - 1:
                    await asyncio.sleep(self.config.burst_interval)

            # Final metrics fetch
            final_metrics = await self._fetch_coalescer_metrics(client)

            # Calculate coalescing metrics
            if initial_metrics and final_metrics:
                initial_merges = initial_metrics.get("batch_coalesce_merges_total", 0)
                final_merges = final_metrics.get("batch_coalesce_merges_total", 0)
                self.metrics.detections_coalesced = int(final_merges - initial_merges)

                initial_calls = initial_metrics.get("batch_llm_calls_total", 0)
                final_calls = final_metrics.get("batch_llm_calls_total", 0)
                self.metrics.total_llm_calls = int(final_calls - initial_calls)

        self.metrics.end_time = time.time()
        return self.metrics

    async def run_priority_test(self) -> BatchMetrics:
        """Run priority scheduling test.

        Submits detections with varied priorities and measures if
        high-priority items are processed faster.

        Returns:
            BatchMetrics with test results
        """
        self.metrics = BatchMetrics()
        self.metrics.start_time = time.time()

        timeout = httpx.Timeout(self.config.timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            # Submit mix of priorities
            detections = []

            # Generate 5 of each priority level
            for object_type in ["gun", "knife"]:  # P0
                for _ in range(5):
                    det = self._generate_detection()
                    det.object_type = object_type
                    det.priority = Priority.P0_CRITICAL
                    detections.append(det)

            for object_type in ["car", "truck"]:  # P1
                for _ in range(5):
                    det = self._generate_detection()
                    det.object_type = object_type
                    det.priority = Priority.P1_HIGH
                    detections.append(det)

            for object_type in ["person"]:  # P2
                for _ in range(10):
                    det = self._generate_detection()
                    det.object_type = object_type
                    det.priority = Priority.P2_NORMAL
                    detections.append(det)

            for object_type in ["dog", "cat"]:  # P3
                for _ in range(5):
                    det = self._generate_detection()
                    det.object_type = object_type
                    det.priority = Priority.P3_LOW
                    detections.append(det)

            # Shuffle to ensure priority scheduling is tested
            random.shuffle(detections)

            # Submit all
            for detection in detections:
                start = time.time()
                await self._submit_detection_via_api(client, detection)
                latency = (time.time() - start) * 1000
                self.metrics.latencies_by_priority[detection.priority].append(latency)

                # Small delay between submissions
                await asyncio.sleep(0.1)

        self.metrics.end_time = time.time()
        return self.metrics


def generate_report(metrics: BatchMetrics, config: LoadTestConfig) -> dict[str, Any]:
    """Generate a comprehensive test report.

    Args:
        metrics: Test metrics
        config: Test configuration

    Returns:
        Report dictionary
    """
    report: dict[str, Any] = {
        "metadata": {
            "timestamp": datetime.now(UTC).isoformat(),
            "mode": config.mode,
            "duration_seconds": config.duration_seconds,
            "requests_per_second": config.requests_per_second,
            "api_url": config.api_url,
        },
        "summary": {
            "total_detections": metrics.total_detections_submitted,
            "total_batches": metrics.total_batches_created,
            "total_llm_calls": metrics.total_llm_calls,
            "detections_coalesced": metrics.detections_coalesced,
            "coalescing_ratio": round(metrics.coalescing_ratio, 3),
            "inference_reduction_pct": round(metrics.inference_reduction_pct, 1),
            "throughput_events_per_min": round(metrics.throughput_events_per_min, 1),
            "test_duration_seconds": round(metrics.end_time - metrics.start_time, 2),
        },
        "latency_by_priority": {},
        "errors": dict(metrics.errors),
    }

    # Add latency stats by priority
    for priority in [
        Priority.P0_CRITICAL,
        Priority.P1_HIGH,
        Priority.P2_NORMAL,
        Priority.P3_LOW,
    ]:
        stats = metrics.get_latency_stats(priority)
        if stats["count"] > 0:
            report["latency_by_priority"][Priority.name(priority)] = stats

    # Add Phase 5 optimization analysis
    report["phase5_analysis"] = analyze_phase5_optimizations(metrics)

    return report


def analyze_phase5_optimizations(metrics: BatchMetrics) -> dict[str, Any]:
    """Analyze Phase 5 optimization effectiveness.

    Args:
        metrics: Test metrics

    Returns:
        Analysis of coalescing and priority scheduling
    """
    analysis: dict[str, Any] = {
        "coalescing": {
            "target_reduction_pct": "20-40%",
            "actual_reduction_pct": round(metrics.inference_reduction_pct, 1),
            "meets_target": 20 <= metrics.inference_reduction_pct <= 100,
        },
        "priority_scheduling": {
            "p0_p50_ms": 0.0,
            "p3_p50_ms": 0.0,
            "priority_respected": False,
        },
    }

    # Check if high priority is faster than low priority
    p0_stats = metrics.get_latency_stats(Priority.P0_CRITICAL)
    p3_stats = metrics.get_latency_stats(Priority.P3_LOW)

    if p0_stats["count"] > 0 and p3_stats["count"] > 0:
        analysis["priority_scheduling"]["p0_p50_ms"] = round(p0_stats["p50"], 2)
        analysis["priority_scheduling"]["p3_p50_ms"] = round(p3_stats["p50"], 2)
        # P0 should be faster (lower latency) than P3
        analysis["priority_scheduling"]["priority_respected"] = p0_stats["p50"] < p3_stats["p50"]

    # Overall assessment
    coalesce_ok = analysis["coalescing"]["meets_target"]
    priority_ok = analysis["priority_scheduling"]["priority_respected"]

    if coalesce_ok and priority_ok:
        analysis["overall"] = "PASS - Both optimizations working"
    elif coalesce_ok:
        analysis["overall"] = "PARTIAL - Coalescing working, priority needs tuning"
    elif priority_ok:
        analysis["overall"] = "PARTIAL - Priority working, coalescing needs tuning"
    else:
        analysis["overall"] = "NEEDS_WORK - Both optimizations need improvement"

    return analysis


def print_report(report: dict[str, Any]) -> None:
    """Print a formatted report to console.

    Args:
        report: Report dictionary
    """
    print("\n" + "=" * 60)
    print("Backend Load Test Results - Phase 5 Optimizations")
    print("=" * 60)

    print("\n--- Test Configuration ---")
    for key, value in report["metadata"].items():
        print(f"  {key}: {value}")

    print("\n--- Summary ---")
    summary = report["summary"]
    print(f"  Total detections submitted: {summary['total_detections']}")
    print(f"  Total batches created: {summary['total_batches']}")
    print(f"  Total LLM calls: {summary['total_llm_calls']}")
    print(f"  Detections coalesced: {summary['detections_coalesced']}")
    print(f"  Coalescing ratio: {summary['coalescing_ratio']}")
    print(f"  Inference reduction: {summary['inference_reduction_pct']}%")
    print(f"  Throughput: {summary['throughput_events_per_min']} events/min")
    print(f"  Test duration: {summary['test_duration_seconds']}s")

    print("\n--- Latency by Priority ---")
    for priority, stats in report["latency_by_priority"].items():
        print(f"  {priority}:")
        print(f"    P50: {stats['p50']:.2f}ms")
        print(f"    P95: {stats['p95']:.2f}ms")
        print(f"    P99: {stats['p99']:.2f}ms")
        print(f"    Mean: {stats['mean']:.2f}ms")
        print(f"    Count: {stats['count']}")

    if report["errors"]:
        print("\n--- Errors ---")
        for error_type, count in report["errors"].items():
            print(f"  {error_type}: {count}")

    print("\n--- Phase 5 Optimization Analysis ---")
    phase5 = report["phase5_analysis"]

    coalesce = phase5["coalescing"]
    print("  Coalescing:")
    print(f"    Target reduction: {coalesce['target_reduction_pct']}")
    print(f"    Actual reduction: {coalesce['actual_reduction_pct']}%")
    print(f"    Meets target: {'YES' if coalesce['meets_target'] else 'NO'}")

    priority = phase5["priority_scheduling"]
    print("  Priority Scheduling:")
    print(f"    P0 (Critical) P50: {priority['p0_p50_ms']}ms")
    print(f"    P3 (Low) P50: {priority['p3_p50_ms']}ms")
    print(f"    Priority respected: {'YES' if priority['priority_respected'] else 'NO'}")

    print(f"\n  Overall Assessment: {phase5['overall']}")
    print("=" * 60 + "\n")


def save_report(report: dict[str, Any], path: Path) -> None:
    """Save report to JSON file.

    Args:
        report: Report dictionary
        path: Output file path
    """
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
        description="Backend load test for Phase 5 batch processing optimizations",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--mode",
        type=str,
        choices=["sustained", "burst", "priority"],
        default="sustained",
        help="Test mode: sustained load, burst testing, or priority validation",
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
        "--api-url",
        type=str,
        default="http://localhost:8000",
        help="Backend API URL",
    )

    parser.add_argument(
        "--burst-size",
        type=int,
        default=20,
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
        default=5,
        help="Total number of bursts to send",
    )

    parser.add_argument(
        "--num-cameras",
        type=int,
        default=4,
        help="Number of simulated cameras",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/backend_load_test_results.json"),
        help="Path to save results JSON",
    )

    parser.add_argument(
        "--same-camera-pct",
        type=float,
        default=0.6,
        help="Percentage of detections from same camera (tests coalescing)",
    )

    return parser.parse_args(args if args is not None else [])


async def main() -> int:
    """Main entry point for backend load testing.

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    args = parse_args()

    config = LoadTestConfig(
        api_url=args.api_url,
        duration_seconds=args.duration,
        requests_per_second=args.rps,
        mode=args.mode,
        burst_size=args.burst_size,
        burst_interval=args.burst_interval,
        total_bursts=args.total_bursts,
        num_cameras=args.num_cameras,
        same_camera_pct=args.same_camera_pct,
    )

    runner = BackendLoadTestRunner(config)

    print(f"Starting backend load test (mode: {args.mode})...")
    print(f"Target: {args.api_url}")

    if args.mode == "sustained":
        print(f"Running sustained load at {args.rps} RPS for {args.duration}s...")
        metrics = await runner.run_sustained_load()
    elif args.mode == "burst":
        print(f"Running burst test: {args.burst_size} requests x {args.total_bursts} bursts...")
        metrics = await runner.run_burst_load()
    else:  # priority
        print("Running priority scheduling validation test...")
        metrics = await runner.run_priority_test()

    # Generate and display report
    report = generate_report(metrics, config)
    print_report(report)

    # Save report
    save_report(report, args.output)
    print(f"Results saved to {args.output}")

    # Return non-zero if Phase 5 optimizations aren't working
    phase5 = report["phase5_analysis"]
    if phase5["overall"].startswith("PASS"):
        return 0
    elif phase5["overall"].startswith("PARTIAL"):
        return 1
    else:
        return 2


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    raise SystemExit(exit_code)
