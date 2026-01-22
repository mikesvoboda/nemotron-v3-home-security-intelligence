#!/usr/bin/env python3
"""
Load testing script for memory profiling.
Generates extensive API load across multiple endpoints.
"""

import argparse
import asyncio
import random
import time
from datetime import datetime

import httpx

BASE_URL = "http://localhost:8000"

# Endpoints to test (GET requests primarily for read load)
GET_ENDPOINTS = [
    # System/health
    "/api/system/health/ready",
    # Cameras
    "/api/cameras",
    "/api/cameras/deleted",
    # Events
    "/api/events",
    "/api/events?page=1&page_size=10",
    "/api/events?page=1&page_size=50",
    # Detections
    "/api/detections",
    "/api/detections?page=1&page_size=10",
    "/api/detections?page=1&page_size=50",
    # Analytics
    "/api/analytics/detection-trends",
    "/api/analytics/object-distribution",
    "/api/analytics/risk-history",
    "/api/analytics/camera-uptime",
    # Calibration
    "/api/calibration",
    "/api/calibration/defaults",
    # Metrics
    "/api/metrics",
    # Debug
    "/api/debug/config",
    "/api/debug/circuit-breakers",
    "/api/debug/pipeline-errors",
    # Audit
    "/api/audit",
    "/api/audit/stats",
    # AI Audit
    "/api/ai-audit/stats",
    "/api/ai-audit/leaderboard",
    "/api/ai-audit/recommendations",
    # Alert rules
    "/api/alerts/rules",
    # Prompts
    "/api/prompts",
    "/api/prompts/active",
    # Jobs
    "/api/jobs",
    # Logs
    "/api/logs/entries",
    "/api/logs/metrics",
    # DLQ
    "/api/dlq",
    "/api/dlq/stats",
]

# POST endpoints that are safe to call
POST_ENDPOINTS = [
    ("/api/debug/memory/gc", {}),  # Trigger garbage collection
]


class LoadStats:
    def __init__(self):
        self.requests = 0
        self.errors = 0
        self.total_time = 0.0
        self.start_time = time.time()

    def record(self, elapsed: float, error: bool = False):
        self.requests += 1
        self.total_time += elapsed
        if error:
            self.errors += 1

    def report(self) -> str:
        elapsed = time.time() - self.start_time
        rps = self.requests / elapsed if elapsed > 0 else 0
        avg_latency = (self.total_time / self.requests * 1000) if self.requests > 0 else 0
        return (
            f"Requests: {self.requests} | Errors: {self.errors} | "
            f"RPS: {rps:.1f} | Avg latency: {avg_latency:.1f}ms"
        )


async def make_request(
    client: httpx.AsyncClient,
    stats: LoadStats,
    endpoint: str,
    method: str = "GET",
    data: dict | None = None,
):
    """Make a single HTTP request and record stats."""
    start = time.time()
    try:
        if method == "GET":
            response = await client.get(f"{BASE_URL}{endpoint}")
        else:
            response = await client.post(f"{BASE_URL}{endpoint}", json=data)
        elapsed = time.time() - start
        stats.record(elapsed, error=response.status_code >= 400)
    except Exception as e:
        elapsed = time.time() - start
        stats.record(elapsed, error=True)


async def worker(
    client: httpx.AsyncClient, stats: LoadStats, stop_event: asyncio.Event, worker_id: int
):
    """Worker that continuously makes requests."""
    while not stop_event.is_set():
        # Randomly pick an endpoint (random module is fine for load testing - not security-sensitive)
        if random.random() < 0.05:  # noqa: S311  # nosemgrep: insecure-random
            endpoint, data = random.choice(POST_ENDPOINTS)  # noqa: S311  # nosemgrep: insecure-random
            await make_request(client, stats, endpoint, "POST", data)
        else:
            endpoint = random.choice(GET_ENDPOINTS)  # noqa: S311  # nosemgrep: insecure-random
            await make_request(client, stats, endpoint, "GET")

        # Small delay to prevent overwhelming (random is fine for jitter)
        await asyncio.sleep(random.uniform(0.01, 0.05))  # noqa: S311  # nosemgrep: insecure-random


def get_backend_memory_mb() -> float | None:
    """Get backend uvicorn worker RSS memory in MB."""
    import subprocess

    # Try multiple patterns to find the uvicorn process
    patterns = [
        "uvicorn.*backend.main:app",  # Most common: uv run uvicorn
        "python.*uvicorn.*backend.main:app",  # Direct python invocation
        "python.*backend.main",  # Direct module execution
    ]

    pids = []
    for pattern in patterns:
        result = subprocess.run(
            ["pgrep", "-f", pattern],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.stdout.strip():
            pids = result.stdout.strip().split("\n")
            break

    if pids:
        # Get the actual worker (highest PID, which is usually the child process)
        # Try each PID in reverse order (highest first)
        for pid in sorted(pids, reverse=True):
            try:
                # Reading /proc/{pid}/status is intentional for memory monitoring
                # nosemgrep: path-traversal-open - pid comes from pgrep, not user input
                with open(f"/proc/{pid}/status") as f:
                    for line in f:
                        if line.startswith("VmRSS:"):
                            rss_kb = int(line.split()[1])
                            return rss_kb / 1024
            except (FileNotFoundError, ValueError, PermissionError):
                continue

    # Couldn't find process or read memory
    return None


async def memory_monitor(stats: LoadStats, stop_event: asyncio.Event):
    """Monitor and report memory usage periodically."""
    initial_memory = None
    while not stop_event.is_set():
        try:
            rss_mb = get_backend_memory_mb()
            if rss_mb is not None:
                if initial_memory is None:
                    initial_memory = rss_mb
                growth = rss_mb - initial_memory
                print(
                    f"[{datetime.now().strftime('%H:%M:%S')}] Memory: {rss_mb:.1f} MB (growth: {growth:+.1f} MB) | {stats.report()}"
                )
            else:
                print(
                    f"[{datetime.now().strftime('%H:%M:%S')}] Could not read memory | {stats.report()}"
                )
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Monitor error: {e}")

        await asyncio.sleep(5)


async def main(duration: int, concurrency: int):
    """Run the load test."""
    print(f"Starting load test: {concurrency} workers for {duration} seconds")
    print(f"Target: {BASE_URL}")
    print("-" * 80)

    stats = LoadStats()
    stop_event = asyncio.Event()

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Start workers and monitor
        workers = [
            asyncio.create_task(worker(client, stats, stop_event, i)) for i in range(concurrency)
        ]
        monitor = asyncio.create_task(memory_monitor(stats, stop_event))

        # Run for specified duration
        await asyncio.sleep(duration)
        stop_event.set()

        # Wait for workers to finish
        await asyncio.gather(*workers, return_exceptions=True)
        monitor.cancel()

    print("-" * 80)
    print(f"Final: {stats.report()}")
    print(f"Total duration: {duration}s")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load test the backend API")
    parser.add_argument("-d", "--duration", type=int, default=60, help="Test duration in seconds")
    parser.add_argument(
        "-c", "--concurrency", type=int, default=10, help="Number of concurrent workers"
    )
    args = parser.parse_args()

    asyncio.run(main(args.duration, args.concurrency))
