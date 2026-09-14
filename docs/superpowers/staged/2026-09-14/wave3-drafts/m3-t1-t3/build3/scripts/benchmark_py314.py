#!/usr/bin/env python3
"""Benchmark suite for Python 3.14 features.

This module provides comprehensive benchmarks for measuring Python 3.14 performance
improvements, including:

- Free-threaded mode (PEP 703) - GIL removal for true parallelism
- UUID7 generation (PEP 778) - Time-ordered UUIDs
- Compression module (Zstd integration)
- General CPU-bound parallel workloads

Usage:
    python scripts/benchmark_py314.py [--iterations N] [--threads N]

Example:
    # Run with default settings
    python scripts/benchmark_py314.py

    # Run with custom iterations
    python scripts/benchmark_py314.py --iterations 50

    # Compare with Python 3.12
    python3.12 scripts/benchmark_py314.py > results_312.txt
    python3.14t scripts/benchmark_py314.py > results_314t.txt
"""

from __future__ import annotations

import argparse
import asyncio
import gc
import json
import statistics
import sys
import time
from collections.abc import Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass
class BenchmarkResult:
    """Result of a single benchmark run."""

    name: str
    iterations: int
    mean_ms: float
    std_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    throughput_ops_sec: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkReport:
    """Complete benchmark report."""

    python_version: str
    python_implementation: str
    free_threading_enabled: bool
    platform: str
    timestamp: str
    results: list[BenchmarkResult]

    def to_dict(self) -> dict[str, Any]:
        """Convert report to dictionary for JSON serialization."""
        return {
            "python_version": self.python_version,
            "python_implementation": self.python_implementation,
            "free_threading_enabled": self.free_threading_enabled,
            "platform": self.platform,
            "timestamp": self.timestamp,
            "results": [asdict(r) for r in self.results],
        }


class Benchmark:
    """Benchmark runner with statistics collection."""

    def __init__(self) -> None:
        """Initialize benchmark runner."""
        self.results: list[BenchmarkResult] = []

    def run_sync(
        self,
        name: str,
        fn: Callable[[], Any],
        iterations: int = 100,
        warmup: int = 5,
        metadata: dict[str, Any] | None = None,
    ) -> BenchmarkResult:
        """Run synchronous benchmark.

        Args:
            name: Name of the benchmark
            fn: Function to benchmark (takes no arguments)
            iterations: Number of iterations to run
            warmup: Number of warmup iterations (not counted)
            metadata: Optional metadata to attach to result

        Returns:
            BenchmarkResult with timing statistics
        """
        # Warmup phase
        for _ in range(warmup):
            fn()

        # Force garbage collection before measurement
        gc.collect()

        times: list[float] = []
        for _ in range(iterations):
            start = time.perf_counter()
            fn()
            elapsed = (time.perf_counter() - start) * 1000  # Convert to ms
            times.append(elapsed)

        result = self._calculate_result(name, iterations, times, metadata or {})
        self.results.append(result)
        return result

    async def run_async(
        self,
        name: str,
        coro_fn: Callable[[], Awaitable[Any]],
        iterations: int = 100,
        warmup: int = 5,
        metadata: dict[str, Any] | None = None,
    ) -> BenchmarkResult:
        """Run async benchmark.

        Args:
            name: Name of the benchmark
            coro_fn: Async function to benchmark
            iterations: Number of iterations to run
            warmup: Number of warmup iterations (not counted)
            metadata: Optional metadata to attach to result

        Returns:
            BenchmarkResult with timing statistics
        """
        # Warmup phase
        for _ in range(warmup):
            await coro_fn()

        gc.collect()

        times: list[float] = []
        for _ in range(iterations):
            start = time.perf_counter()
            await coro_fn()
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)

        result = self._calculate_result(name, iterations, times, metadata or {})
        self.results.append(result)
        return result

    def _calculate_result(
        self,
        name: str,
        iterations: int,
        times: list[float],
        metadata: dict[str, Any],
    ) -> BenchmarkResult:
        """Calculate statistics from timing data."""
        sorted_times = sorted(times)
        n = len(times)

        mean = statistics.mean(times)
        std = statistics.stdev(times) if n > 1 else 0.0

        # Percentile indices (0-based)
        p50_idx = int(0.50 * n)
        p95_idx = min(int(0.95 * n), n - 1)
        p99_idx = min(int(0.99 * n), n - 1)

        return BenchmarkResult(
            name=name,
            iterations=iterations,
            mean_ms=mean,
            std_ms=std,
            p50_ms=sorted_times[p50_idx],
            p95_ms=sorted_times[p95_idx],
            p99_ms=sorted_times[p99_idx],
            throughput_ops_sec=1000.0 / mean if mean > 0 else 0.0,
            metadata=metadata,
        )

    def print_results(self) -> None:
        """Print benchmark results in a formatted table."""
        print("\n" + "=" * 90)
        print("BENCHMARK RESULTS")
        print("=" * 90)
        header = f"{'Name':<40} {'Mean (ms)':<12} {'Std (ms)':<10} {'P95 (ms)':<12} {'Ops/sec':<12}"
        print(header)
        print("-" * 90)
        for r in self.results:
            print(
                f"{r.name:<40} {r.mean_ms:<12.3f} {r.std_ms:<10.3f} "
                f"{r.p95_ms:<12.3f} {r.throughput_ops_sec:<12.1f}"
            )
        print("=" * 90)

    def create_report(self) -> BenchmarkReport:
        """Create a complete benchmark report."""
        import platform

        return BenchmarkReport(
            python_version=sys.version,
            python_implementation=sys.implementation.name,
            free_threading_enabled=check_free_threading(),
            platform=platform.platform(),
            timestamp=datetime.now(UTC).isoformat(),
            results=self.results,
        )


def check_free_threading() -> bool:
    """Check if running in free-threaded mode (GIL disabled).

    Python 3.14+ with free-threading enabled will have GIL disabled,
    allowing true parallel execution of Python threads.

    Returns:
        True if GIL is disabled (free-threaded mode), False otherwise
    """
    if hasattr(sys, "_is_gil_enabled"):
        return not sys._is_gil_enabled()
    return False


def get_python_features() -> dict[str, bool]:
    """Detect available Python 3.14 features.

    Returns:
        Dictionary mapping feature names to availability
    """
    features: dict[str, bool] = {}

    # Check for free-threading (PEP 703)
    features["free_threading"] = check_free_threading()

    # Check for UUID7 (PEP 778)
    import uuid

    features["uuid7"] = hasattr(uuid, "uuid7")

    # Check for compression module (Zstd)
    try:
        import compression.zstd  # noqa: F401

        features["compression_zstd"] = True
    except ImportError:
        features["compression_zstd"] = False

    # Check for improved error messages (always true in 3.14)
    features["improved_errors"] = sys.version_info >= (3, 14)

    return features


# =============================================================================
# Benchmark Functions
# =============================================================================


def benchmark_cpu_parallel(num_threads: int = 4, work_size: int = 1000000) -> list[int]:
    """Benchmark CPU-bound work in parallel threads.

    This benchmark measures the effectiveness of parallel thread execution.
    With free-threading enabled (GIL disabled), CPU-bound work should scale
    linearly with the number of threads.

    Args:
        num_threads: Number of parallel threads
        work_size: Amount of work per thread

    Returns:
        List of results from each thread
    """

    def cpu_work() -> int:
        """CPU-intensive computation."""
        total = 0
        for i in range(work_size):
            total += i * i % 1000
        return total

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(cpu_work) for _ in range(num_threads)]
        results = [f.result() for f in futures]
    return results


def benchmark_cpu_serial(work_size: int = 1000000, iterations: int = 4) -> list[int]:
    """Benchmark CPU-bound work serially for comparison.

    Args:
        work_size: Amount of work per iteration
        iterations: Number of serial iterations

    Returns:
        List of results
    """
    results: list[int] = []
    for _ in range(iterations):
        total = 0
        for i in range(work_size):
            total += i * i % 1000
        results.append(total)
    return results


def benchmark_compression(data_size: int = 100000) -> tuple[int, int] | None:
    """Benchmark Zstd compression (Python 3.14+).

    Args:
        data_size: Size of data to compress

    Returns:
        Tuple of (compressed_size, decompressed_size) or None if unavailable
    """
    try:
        from compression import zstd

        # Create compressible data
        data = b"x" * data_size
        compressed = zstd.compress(data)
        decompressed = zstd.decompress(compressed)
        return len(compressed), len(decompressed)
    except ImportError:
        return None


def benchmark_uuid_generation(count: int = 1000) -> dict[str, int]:
    """Benchmark UUID generation comparing UUID4 vs UUID7.

    UUID7 (PEP 778) provides time-ordered UUIDs, which are better for
    database indexing and distributed systems.

    Args:
        count: Number of UUIDs to generate

    Returns:
        Dictionary with counts of generated UUIDs
    """
    import uuid

    results: dict[str, int] = {}

    # Generate UUID4 (random)
    uuid4_ids = [uuid.uuid4() for _ in range(count)]
    results["uuid4"] = len(uuid4_ids)

    # Generate UUID7 (time-ordered, Python 3.14+)
    try:
        uuid7_ids = [uuid.uuid7() for _ in range(count)]
        results["uuid7"] = len(uuid7_ids)
    except AttributeError:
        results["uuid7"] = 0

    return results


async def benchmark_async_gather(task_count: int = 100) -> list[int]:
    """Benchmark asyncio.gather with many tasks.

    Args:
        task_count: Number of concurrent tasks

    Returns:
        List of task results
    """

    async def async_task(n: int) -> int:
        """Simulated async task."""
        await asyncio.sleep(0)  # Yield to event loop
        return n * 2

    tasks = [async_task(i) for i in range(task_count)]
    results = await asyncio.gather(*tasks)
    return list(results)


def benchmark_dict_operations(size: int = 10000) -> int:
    """Benchmark dictionary operations (improved in 3.14).

    Args:
        size: Number of dictionary entries

    Returns:
        Final dictionary size
    """
    d: dict[int, int] = {}

    # Insertions
    for i in range(size):
        d[i] = i * 2

    # Lookups
    total = 0
    for i in range(size):
        total += d.get(i, 0)

    # Updates
    for i in range(0, size, 2):
        d[i] = i * 3

    # Deletions
    for i in range(0, size, 4):
        del d[i]

    return len(d)


def benchmark_list_comprehension(size: int = 100000) -> int:
    """Benchmark list comprehension performance.

    Args:
        size: Number of elements

    Returns:
        Sum of resulting list
    """
    result = [x * 2 + 1 for x in range(size) if x % 2 == 0]
    return sum(result)


def benchmark_exception_handling(iterations: int = 10000) -> int:
    """Benchmark exception handling overhead.

    Python 3.14 has improved exception handling performance.

    Args:
        iterations: Number of try/except iterations

    Returns:
        Count of caught exceptions
    """
    caught = 0
    for i in range(iterations):
        try:
            if i % 10 == 0:
                raise ValueError(f"Test exception {i}")
        except ValueError:
            caught += 1
    return caught


async def main(args: argparse.Namespace) -> None:
    """Run all benchmarks."""
    bench = Benchmark()

    # Print system info
    print("=" * 90)
    print("PYTHON 3.14 BENCHMARK SUITE")
    print("=" * 90)
    print(f"Python version: {sys.version}")
    print(f"Implementation: {sys.implementation.name}")
    print(f"Free-threading enabled: {check_free_threading()}")
    print()

    # Detect features
    features = get_python_features()
    print("Available Features:")
    for feature, available in features.items():
        status = "YES" if available else "NO"
        print(f"  - {feature}: {status}")
    print()

    iterations = args.iterations
    num_threads = args.threads

    print(f"Running benchmarks with {iterations} iterations...")
    print()

    # ==========================================================================
    # CPU Parallel Benchmarks (most important for free-threading)
    # ==========================================================================

    print(">>> CPU Parallel Benchmarks")

    # Serial baseline
    bench.run_sync(
        "CPU serial (4 iterations)",
        lambda: benchmark_cpu_serial(500000, 4),
        iterations=iterations,
        metadata={"type": "cpu_serial", "work_size": 500000, "iterations": 4},
    )

    # Parallel with varying thread counts
    for threads in [2, 4, 8]:
        if threads <= num_threads:
            bench.run_sync(
                f"CPU parallel ({threads} threads)",
                lambda t=threads: benchmark_cpu_parallel(t, 500000),
                iterations=iterations,
                metadata={"type": "cpu_parallel", "threads": threads, "work_size": 500000},
            )

    # ==========================================================================
    # UUID Benchmarks
    # ==========================================================================

    print(">>> UUID Benchmarks")

    bench.run_sync(
        "UUID4 generation (1000)",
        lambda: [__import__("uuid").uuid4() for _ in range(1000)],
        iterations=iterations,
        metadata={"type": "uuid4", "count": 1000},
    )

    if features["uuid7"]:
        bench.run_sync(
            "UUID7 generation (1000)",
            lambda: [__import__("uuid").uuid7() for _ in range(1000)],
            iterations=iterations,
            metadata={"type": "uuid7", "count": 1000},
        )

    # ==========================================================================
    # Compression Benchmarks
    # ==========================================================================

    if features["compression_zstd"]:
        print(">>> Compression Benchmarks")

        bench.run_sync(
            "Zstd compress 100KB",
            lambda: benchmark_compression(100000),
            iterations=iterations,
            metadata={"type": "compression", "size": 100000},
        )

        bench.run_sync(
            "Zstd compress 1MB",
            lambda: benchmark_compression(1000000),
            iterations=max(iterations // 2, 10),
            metadata={"type": "compression", "size": 1000000},
        )

    # ==========================================================================
    # Async Benchmarks
    # ==========================================================================

    print(">>> Async Benchmarks")

    await bench.run_async(
        "asyncio.gather (100 tasks)",
        lambda: benchmark_async_gather(100),
        iterations=iterations,
        metadata={"type": "async_gather", "tasks": 100},
    )

    await bench.run_async(
        "asyncio.gather (1000 tasks)",
        lambda: benchmark_async_gather(1000),
        iterations=iterations,
        metadata={"type": "async_gather", "tasks": 1000},
    )

    # ==========================================================================
    # General Python Performance
    # ==========================================================================

    print(">>> General Performance Benchmarks")

    bench.run_sync(
        "Dict operations (10k entries)",
        lambda: benchmark_dict_operations(10000),
        iterations=iterations,
        metadata={"type": "dict_ops", "size": 10000},
    )

    bench.run_sync(
        "List comprehension (100k)",
        lambda: benchmark_list_comprehension(100000),
        iterations=iterations,
        metadata={"type": "list_comp", "size": 100000},
    )

    bench.run_sync(
        "Exception handling (10k)",
        lambda: benchmark_exception_handling(10000),
        iterations=iterations,
        metadata={"type": "exception", "iterations": 10000},
    )

    # ==========================================================================
    # Results
    # ==========================================================================

    bench.print_results()

    # Save JSON report if requested
    if args.output:
        report = bench.create_report()
        output_path = Path(args.output)
        output_path.write_text(json.dumps(report.to_dict(), indent=2))
        print(f"\nReport saved to: {output_path}")

    # Print free-threading analysis
    if check_free_threading():
        print("\n" + "=" * 90)
        print("FREE-THREADING ANALYSIS")
        print("=" * 90)
        print("GIL is DISABLED - True parallel Python thread execution is enabled.")
        print("CPU-bound work should scale with thread count.")
        print()
        print("Expected speedups:")
        print("  - 2 threads: ~1.8-2.0x over serial")
        print("  - 4 threads: ~3.5-4.0x over serial")
        print("  - 8 threads: ~6.0-8.0x over serial (depends on CPU cores)")
        print("=" * 90)
    else:
        print("\n" + "=" * 90)
        print("NOTE: Running with GIL enabled")
        print("=" * 90)
        print("To enable free-threading, use Python 3.14t (free-threaded build):")
        print("  python3.14t scripts/benchmark_py314.py")
        print("=" * 90)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Benchmark suite for Python 3.14 features",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run with defaults
    python scripts/benchmark_py314.py

    # Run with more iterations for accurate results
    python scripts/benchmark_py314.py --iterations 100

    # Save results to JSON
    python scripts/benchmark_py314.py --output results.json

    # Compare Python versions
    python3.12 scripts/benchmark_py314.py --output results_312.json
    python3.14t scripts/benchmark_py314.py --output results_314t.json
        """,
    )

    parser.add_argument(
        "--iterations",
        "-i",
        type=int,
        default=20,
        help="Number of iterations per benchmark (default: 20)",
    )

    parser.add_argument(
        "--threads",
        "-t",
        type=int,
        default=8,
        help="Maximum number of threads for parallel benchmarks (default: 8)",
    )

    parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="Output file for JSON report",
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main(args))
