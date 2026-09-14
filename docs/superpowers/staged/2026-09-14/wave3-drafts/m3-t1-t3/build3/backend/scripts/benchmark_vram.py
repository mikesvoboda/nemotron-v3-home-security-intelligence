#!/usr/bin/env python3
"""VRAM Usage Benchmarking Script for Vision Extraction Models.

This script measures VRAM consumption and loading times for all models
in the Model Zoo. Run it on a system with a GPU to understand the VRAM
requirements of the vision extraction pipeline.

Usage:
    cd backend
    python scripts/benchmark_vram.py

The script will:
1. Measure baseline GPU VRAM usage
2. Load each enabled model individually and measure:
   - Loading time (seconds)
   - VRAM consumption (MB)
   - Model availability status
3. Generate a summary report

Requirements:
    - NVIDIA GPU with CUDA support
    - pynvml or nvidia-smi for VRAM monitoring
    - Model dependencies (transformers, ultralytics, etc.)
"""

from __future__ import annotations

import asyncio
import gc
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC
from pathlib import Path
from typing import TYPE_CHECKING

# Add backend to path for imports
backend_path = Path(__file__).parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

if TYPE_CHECKING:
    from services.model_zoo import ModelConfig


@dataclass(slots=True)
class BenchmarkResult:
    """Result of benchmarking a single model."""

    model_name: str
    category: str
    estimated_vram_mb: int
    actual_vram_mb: int | None = None
    loading_time_seconds: float | None = None
    unloading_time_seconds: float | None = None
    success: bool = False
    error: str | None = None


@dataclass(slots=True)
class BenchmarkReport:
    """Complete benchmark report for all models."""

    baseline_vram_mb: int
    total_gpu_memory_mb: int
    results: list[BenchmarkResult] = field(default_factory=list)
    timestamp: str = ""

    def to_markdown(self) -> str:
        """Generate markdown report."""
        lines = [
            "# VRAM Benchmark Report",
            "",
            f"**Timestamp:** {self.timestamp}",
            f"**GPU Total Memory:** {self.total_gpu_memory_mb:,} MB",
            f"**Baseline VRAM Usage:** {self.baseline_vram_mb:,} MB",
            f"**Available for Models:** {self.total_gpu_memory_mb - self.baseline_vram_mb:,} MB",
            "",
            "## Model Results",
            "",
            "| Model | Category | Est. VRAM | Actual VRAM | Load Time | Status |",
            "|-------|----------|-----------|-------------|-----------|--------|",
        ]

        for r in self.results:
            actual = f"{r.actual_vram_mb:,} MB" if r.actual_vram_mb is not None else "N/A"
            load_time = f"{r.loading_time_seconds:.2f}s" if r.loading_time_seconds else "N/A"
            status = "OK" if r.success else f"FAIL: {r.error}"
            lines.append(
                f"| {r.model_name} | {r.category} | {r.estimated_vram_mb:,} MB | "
                f"{actual} | {load_time} | {status} |"
            )

        lines.extend(
            [
                "",
                "## Summary",
                "",
            ]
        )

        successful = [r for r in self.results if r.success]
        failed = [r for r in self.results if not r.success]

        lines.append(f"- **Successful loads:** {len(successful)}/{len(self.results)}")
        if successful:
            total_vram = sum(r.actual_vram_mb for r in successful if r.actual_vram_mb)
            avg_load_time = sum(
                r.loading_time_seconds for r in successful if r.loading_time_seconds
            ) / len(successful)
            lines.append(f"- **Total VRAM (all models):** {total_vram:,} MB")
            lines.append(
                f"- **Peak VRAM (single model):** {max(r.actual_vram_mb or 0 for r in successful):,} MB"
            )
            lines.append(f"- **Average load time:** {avg_load_time:.2f}s")

        if failed:
            lines.append(f"- **Failed models:** {', '.join(r.model_name for r in failed)}")

        return "\n".join(lines)


def get_gpu_memory() -> tuple[int, int]:
    """Get current GPU memory usage and total memory.

    Returns:
        Tuple of (used_mb, total_mb)
    """
    try:
        import pynvml

        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        pynvml.nvmlShutdown()
        return info.used // (1024 * 1024), info.total // (1024 * 1024)
    except ImportError:
        # Fall back to nvidia-smi
        import subprocess

        result = subprocess.run(
            [
                "/usr/bin/nvidia-smi",
                "--query-gpu=memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        used, total = result.stdout.strip().split(",")
        return int(used.strip()), int(total.strip())
    except Exception as e:
        print(f"Warning: Could not get GPU memory: {e}")
        return 0, 0


def clear_gpu_cache() -> None:
    """Clear GPU memory caches."""
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
    except ImportError:
        # torch not installed - no CUDA cache to clear.
        # Benchmark continues without CUDA cleanup.
        # See: NEM-2540 for rationale
        pass


async def benchmark_model(
    model_name: str,
    model_config: ModelConfig,
    baseline_vram: int,
) -> BenchmarkResult:
    """Benchmark a single model.

    Args:
        model_name: Name of the model
        model_config: Model configuration
        baseline_vram: Baseline VRAM before loading

    Returns:
        BenchmarkResult with timing and memory data
    """

    result = BenchmarkResult(
        model_name=model_name,
        category=model_config.category,
        estimated_vram_mb=model_config.vram_mb,
    )

    if not model_config.enabled:
        result.error = "Model disabled"
        return result

    try:
        print(f"  Loading {model_name}...", end="", flush=True)

        # Clear caches before loading
        clear_gpu_cache()

        # Measure loading time
        start_time = time.monotonic()
        model = await model_config.load_fn(model_config.path)
        load_time = time.monotonic() - start_time

        # Measure VRAM after loading
        used_vram, _ = get_gpu_memory()
        actual_vram = used_vram - baseline_vram

        result.loading_time_seconds = load_time
        result.actual_vram_mb = max(actual_vram, 0)  # Ensure non-negative
        result.success = True

        print(f" OK ({load_time:.2f}s, {actual_vram:,} MB)")

        # Unload model and measure unload time
        start_time = time.monotonic()
        del model
        clear_gpu_cache()
        unload_time = time.monotonic() - start_time
        result.unloading_time_seconds = unload_time

    except Exception as e:
        print(f" FAILED: {e}")
        result.error = str(e)[:100]  # Truncate long errors

    return result


async def run_benchmark() -> BenchmarkReport:
    """Run the complete benchmark suite.

    Returns:
        BenchmarkReport with all results
    """
    from datetime import datetime

    from services.model_zoo import get_model_zoo

    print("=" * 60)
    print("VRAM Benchmark for Vision Extraction Models")
    print("=" * 60)
    print()

    # Get baseline memory
    print("Measuring baseline GPU memory...")
    clear_gpu_cache()
    baseline_vram, total_vram = get_gpu_memory()
    print(f"  Total GPU Memory: {total_vram:,} MB")
    print(f"  Baseline VRAM: {baseline_vram:,} MB")
    print(f"  Available: {total_vram - baseline_vram:,} MB")
    print()

    report = BenchmarkReport(
        baseline_vram_mb=baseline_vram,
        total_gpu_memory_mb=total_vram,
        timestamp=datetime.now(UTC).isoformat(),
    )

    # Get all models from the zoo
    zoo = get_model_zoo()
    enabled_models = {name: config for name, config in zoo.items() if config.enabled}

    print(f"Benchmarking {len(enabled_models)} enabled models...")
    print()

    for model_name, model_config in enabled_models.items():
        # Reset to baseline before each model
        clear_gpu_cache()

        result = await benchmark_model(model_name, model_config, baseline_vram)
        report.results.append(result)

        # Wait a moment for GPU to settle
        await asyncio.sleep(0.5)

    return report


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success)
    """
    # Check for GPU
    _used, total = get_gpu_memory()
    if total == 0:
        print("Error: No GPU detected or unable to query GPU memory.")
        print("This benchmark requires an NVIDIA GPU with CUDA support.")
        return 1

    # Run benchmark
    report = asyncio.run(run_benchmark())

    # Print report
    print()
    print("=" * 60)
    print("BENCHMARK COMPLETE")
    print("=" * 60)
    print()
    print(report.to_markdown())

    # Save report to file
    output_path = Path(__file__).parent.parent.parent / "docs" / "vram-benchmark.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report.to_markdown())
    print()
    print(f"Report saved to: {output_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
