#!/usr/bin/env python3
"""Benchmark YOLO26 vs YOLO26 latency and throughput.

This script compares YOLO26 model variants (n, s, m) against YOLO26 for:
- Inference latency (ms)
- Throughput (FPS) at different batch sizes
- GPU memory usage (VRAM)
- CPU usage

Usage:
    # Run full benchmark (GPU)
    uv run python scripts/benchmark_yolo26_latency.py

    # Run specific models only
    uv run python scripts/benchmark_yolo26_latency.py --models yolo26n,yolo26s

    # Run CPU benchmark only
    uv run python scripts/benchmark_yolo26_latency.py --device cpu

    # Custom output path
    uv run python scripts/benchmark_yolo26_latency.py --output docs/benchmarks/my-results.md

    # Test specific resolutions
    uv run python scripts/benchmark_yolo26_latency.py --resolutions 640,1280

Environment Variables:
    YOLO26_MODEL_PATH: Override YOLO26 model directory (default: /export/ai_models/model-zoo/yolo26)
    YOLO26_MODEL_PATH: Override YOLO26 model path (default: /export/ai_models/yolo26v2/yolo26_v2_r101vd)
"""

from __future__ import annotations

import argparse
import gc
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

# Model paths
YOLO26_MODEL_DIR = Path(os.environ.get("YOLO26_MODEL_PATH", "/export/ai_models/model-zoo/yolo26"))
YOLO26_MODEL_PATH = Path(
    os.environ.get("YOLO26_MODEL_PATH", "/export/ai_models/yolo26v2/yolo26_v2_r101vd")
)

# Benchmark configuration
DEFAULT_BATCH_SIZES = [1, 4, 8, 16]
DEFAULT_RESOLUTIONS = [(640, 640), (1280, 1280)]
DEFAULT_WARMUP_ITERATIONS = 10
DEFAULT_BENCHMARK_ITERATIONS = 100


@dataclass
class LatencyMetrics:
    """Latency metrics for a single inference."""

    preprocess_ms: float
    inference_ms: float
    postprocess_ms: float
    total_ms: float


@dataclass
class BenchmarkResult:
    """Result of benchmarking a single model configuration."""

    model_name: str
    resolution: tuple[int, int]
    device: str
    batch_size: int

    # Latency metrics (single image)
    latency_mean_ms: float
    latency_std_ms: float
    latency_min_ms: float
    latency_max_ms: float
    latency_p50_ms: float
    latency_p95_ms: float
    latency_p99_ms: float

    # Component breakdown (for batch_size=1)
    preprocess_mean_ms: float = 0.0
    inference_mean_ms: float = 0.0
    postprocess_mean_ms: float = 0.0

    # Throughput
    throughput_fps: float = 0.0

    # Memory usage
    vram_used_mb: float = 0.0
    vram_peak_mb: float = 0.0

    # Model info
    parameters_m: float = 0.0
    model_size_mb: float = 0.0

    # Error tracking
    error: str | None = None


@dataclass
class ModelBenchmarkSummary:
    """Summary of all benchmarks for a single model."""

    model_name: str
    model_type: str  # "yolo26" or "yolo26"
    parameters_m: float
    model_size_mb: float
    results: list[BenchmarkResult] = field(default_factory=list)


def get_gpu_memory_mb() -> tuple[float, float]:
    """Get current and peak GPU memory usage in MB using nvidia-smi.

    Returns:
        Tuple of (current_usage_mb, peak_usage_mb)
    """
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            check=True,
        )
        current = float(result.stdout.strip().split("\n")[0])

        # Try to get peak memory if available
        try:
            import torch

            if torch.cuda.is_available():
                peak = torch.cuda.max_memory_allocated() / (1024 * 1024)
                return current, peak
        except ImportError:
            pass

        return current, current
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
        return 0.0, 0.0


def get_gpu_info() -> dict[str, Any]:
    """Get GPU information."""
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,driver_version,cuda_version",
                "--format=csv,noheader",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        parts = result.stdout.strip().split(", ")
        return {
            "name": parts[0] if len(parts) > 0 else "Unknown",
            "memory_total_mb": int(parts[1].replace(" MiB", "")) if len(parts) > 1 else 0,
            "driver_version": parts[2] if len(parts) > 2 else "Unknown",
            "cuda_version": parts[3] if len(parts) > 3 else "Unknown",
        }
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
        return {
            "name": "Unknown",
            "memory_total_mb": 0,
            "driver_version": "Unknown",
            "cuda_version": "Unknown",
        }


def create_test_image(width: int = 640, height: int = 640) -> Image.Image:
    """Create a realistic test image for benchmarking."""
    np.random.seed(42)
    # Create image with some realistic variation
    data = np.random.randint(80, 180, (height, width, 3), dtype=np.uint8)
    # Add some rectangular regions (simulating objects)
    data[100:300, 150:400] = [180, 160, 140]
    data[350:500, 200:450] = [140, 180, 160]
    return Image.fromarray(data)


def benchmark_yolo26_model(
    model_path: Path,
    resolution: tuple[int, int],
    batch_sizes: list[int],
    device: str,
    warmup_iterations: int,
    benchmark_iterations: int,
) -> list[BenchmarkResult]:
    """Benchmark a YOLO26 model."""
    try:
        from ultralytics import YOLO
    except ImportError:
        print("Error: ultralytics package not installed. Install with: pip install ultralytics")
        sys.exit(1)

    import torch

    results = []
    model_name = model_path.stem

    print(f"\n{'=' * 60}")
    print(f"Benchmarking {model_name} at {resolution[0]}x{resolution[1]} on {device}")
    print(f"{'=' * 60}")

    try:
        # Load model
        model = YOLO(str(model_path))

        # Get model info
        model_size_mb = model_path.stat().st_size / (1024 * 1024)
        parameters_m = sum(p.numel() for p in model.model.parameters()) / 1e6

        # Clear GPU cache and reset peak memory tracking
        gc.collect()
        if device.startswith("cuda") and torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats()
            torch.cuda.synchronize()

        # Create test images
        test_image = create_test_image(resolution[0], resolution[1])

        for batch_size in batch_sizes:
            print(f"\n  Batch size: {batch_size}")

            # Create batch
            images = [test_image] * batch_size

            # Warmup
            print(f"    Warming up ({warmup_iterations} iterations)...")
            for _ in range(warmup_iterations):
                _ = model.predict(images, imgsz=resolution[0], device=device, verbose=False)

            if device.startswith("cuda") and torch.cuda.is_available():
                torch.cuda.synchronize()

            # Benchmark
            print(f"    Benchmarking ({benchmark_iterations} iterations)...")
            latencies = []
            preprocess_times = []
            inference_times = []
            postprocess_times = []

            for i in range(benchmark_iterations):
                # Clear cache periodically to prevent memory buildup
                if i % 20 == 0 and device.startswith("cuda") and torch.cuda.is_available():
                    torch.cuda.empty_cache()

                start_total = time.perf_counter()

                # Run inference - YOLO handles preprocessing internally
                results_batch = model.predict(
                    images, imgsz=resolution[0], device=device, verbose=False
                )

                if device.startswith("cuda") and torch.cuda.is_available():
                    torch.cuda.synchronize()

                end_total = time.perf_counter()

                total_ms = (end_total - start_total) * 1000
                latencies.append(total_ms)

                # Extract timing info from YOLO results if available
                if hasattr(results_batch[0], "speed"):
                    speed = results_batch[0].speed
                    preprocess_times.append(speed.get("preprocess", 0))
                    inference_times.append(speed.get("inference", 0))
                    postprocess_times.append(speed.get("postprocess", 0))

            # Calculate statistics
            latencies = np.array(latencies)
            latency_per_image = latencies / batch_size

            vram_current, vram_peak = get_gpu_memory_mb()

            result = BenchmarkResult(
                model_name=model_name,
                resolution=resolution,
                device=device,
                batch_size=batch_size,
                latency_mean_ms=float(np.mean(latency_per_image)),
                latency_std_ms=float(np.std(latency_per_image)),
                latency_min_ms=float(np.min(latency_per_image)),
                latency_max_ms=float(np.max(latency_per_image)),
                latency_p50_ms=float(np.percentile(latency_per_image, 50)),
                latency_p95_ms=float(np.percentile(latency_per_image, 95)),
                latency_p99_ms=float(np.percentile(latency_per_image, 99)),
                preprocess_mean_ms=float(np.mean(preprocess_times)) if preprocess_times else 0.0,
                inference_mean_ms=float(np.mean(inference_times)) if inference_times else 0.0,
                postprocess_mean_ms=float(np.mean(postprocess_times)) if postprocess_times else 0.0,
                throughput_fps=batch_size * 1000 / float(np.mean(latencies)),
                vram_used_mb=vram_current,
                vram_peak_mb=vram_peak,
                parameters_m=parameters_m,
                model_size_mb=model_size_mb,
            )

            print(
                f"    Latency: {result.latency_mean_ms:.2f} +/- {result.latency_std_ms:.2f} ms/image"
            )
            print(f"    Throughput: {result.throughput_fps:.1f} FPS")
            print(f"    VRAM: {result.vram_used_mb:.0f} MB (peak: {result.vram_peak_mb:.0f} MB)")

            results.append(result)

        # Cleanup
        del model
        gc.collect()
        if device.startswith("cuda") and torch.cuda.is_available():
            torch.cuda.empty_cache()

    except Exception as e:
        print(f"  ERROR: {e}")
        results.append(
            BenchmarkResult(
                model_name=model_name,
                resolution=resolution,
                device=device,
                batch_size=1,
                latency_mean_ms=0,
                latency_std_ms=0,
                latency_min_ms=0,
                latency_max_ms=0,
                latency_p50_ms=0,
                latency_p95_ms=0,
                latency_p99_ms=0,
                error=str(e),
            )
        )

    return results


def benchmark_yolo26_model(
    model_path: Path,
    resolution: tuple[int, int],
    batch_sizes: list[int],
    device: str,
    warmup_iterations: int,
    benchmark_iterations: int,
) -> list[BenchmarkResult]:
    """Benchmark YOLO26 model using HuggingFace Transformers."""
    try:
        import torch
        from transformers import AutoImageProcessor, AutoModelForObjectDetection
    except ImportError:
        print("Error: transformers package not installed. Install with: pip install transformers")
        sys.exit(1)

    results = []
    model_name = "yolo26-v2-r101vd"

    print(f"\n{'=' * 60}")
    print(f"Benchmarking {model_name} at {resolution[0]}x{resolution[1]} on {device}")
    print(f"{'=' * 60}")

    try:
        # Load model and processor
        print("  Loading model...")
        processor = AutoImageProcessor.from_pretrained(str(model_path))

        try:
            model = AutoModelForObjectDetection.from_pretrained(
                str(model_path), attn_implementation="sdpa"
            )
            print("  Using SDPA attention (optimized)")
        except (ValueError, ImportError):
            model = AutoModelForObjectDetection.from_pretrained(str(model_path))
            print("  Using default attention")

        # Get model info
        parameters_m = sum(p.numel() for p in model.parameters()) / 1e6
        # Estimate model size from parameters (assuming FP32)
        model_size_mb = parameters_m * 4  # 4 bytes per FP32 parameter

        # Move to device
        if device.startswith("cuda") and torch.cuda.is_available():
            model = model.to(device)
        model.eval()

        # Clear GPU cache and reset peak memory tracking
        gc.collect()
        if device.startswith("cuda") and torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats()
            torch.cuda.synchronize()

        # Create test images
        test_image = create_test_image(resolution[0], resolution[1])

        for batch_size in batch_sizes:
            print(f"\n  Batch size: {batch_size}")

            # Create batch
            images = [test_image] * batch_size

            # Warmup
            print(f"    Warming up ({warmup_iterations} iterations)...")
            for _ in range(warmup_iterations):
                inputs = processor(images=images, return_tensors="pt")
                if device.startswith("cuda"):
                    inputs = {k: v.to(device) for k, v in inputs.items()}
                with torch.inference_mode():
                    _ = model(**inputs)

            if device.startswith("cuda") and torch.cuda.is_available():
                torch.cuda.synchronize()

            # Benchmark
            print(f"    Benchmarking ({benchmark_iterations} iterations)...")
            latencies = []
            preprocess_times = []
            inference_times = []
            postprocess_times = []

            for i in range(benchmark_iterations):
                # Clear cache periodically
                if i % 20 == 0 and device.startswith("cuda") and torch.cuda.is_available():
                    torch.cuda.empty_cache()

                # Preprocessing
                start_preprocess = time.perf_counter()
                inputs = processor(images=images, return_tensors="pt")
                if device.startswith("cuda"):
                    inputs = {k: v.to(device) for k, v in inputs.items()}
                end_preprocess = time.perf_counter()

                # Inference
                start_inference = time.perf_counter()
                with torch.inference_mode():
                    outputs = model(**inputs)
                if device.startswith("cuda") and torch.cuda.is_available():
                    torch.cuda.synchronize()
                end_inference = time.perf_counter()

                # Postprocessing
                start_postprocess = time.perf_counter()
                target_sizes = torch.tensor([[resolution[1], resolution[0]]] * batch_size)
                if device.startswith("cuda"):
                    target_sizes = target_sizes.to(device)
                _ = processor.post_process_object_detection(
                    outputs, target_sizes=target_sizes, threshold=0.5
                )
                end_postprocess = time.perf_counter()

                preprocess_ms = (end_preprocess - start_preprocess) * 1000
                inference_ms = (end_inference - start_inference) * 1000
                postprocess_ms = (end_postprocess - start_postprocess) * 1000
                total_ms = preprocess_ms + inference_ms + postprocess_ms

                latencies.append(total_ms)
                preprocess_times.append(preprocess_ms)
                inference_times.append(inference_ms)
                postprocess_times.append(postprocess_ms)

            # Calculate statistics
            latencies = np.array(latencies)
            latency_per_image = latencies / batch_size

            vram_current, vram_peak = get_gpu_memory_mb()

            result = BenchmarkResult(
                model_name=model_name,
                resolution=resolution,
                device=device,
                batch_size=batch_size,
                latency_mean_ms=float(np.mean(latency_per_image)),
                latency_std_ms=float(np.std(latency_per_image)),
                latency_min_ms=float(np.min(latency_per_image)),
                latency_max_ms=float(np.max(latency_per_image)),
                latency_p50_ms=float(np.percentile(latency_per_image, 50)),
                latency_p95_ms=float(np.percentile(latency_per_image, 95)),
                latency_p99_ms=float(np.percentile(latency_per_image, 99)),
                preprocess_mean_ms=float(np.mean(preprocess_times)) / batch_size,
                inference_mean_ms=float(np.mean(inference_times)) / batch_size,
                postprocess_mean_ms=float(np.mean(postprocess_times)) / batch_size,
                throughput_fps=batch_size * 1000 / float(np.mean(latencies)),
                vram_used_mb=vram_current,
                vram_peak_mb=vram_peak,
                parameters_m=parameters_m,
                model_size_mb=model_size_mb,
            )

            print(
                f"    Latency: {result.latency_mean_ms:.2f} +/- {result.latency_std_ms:.2f} ms/image"
            )
            print(f"    Throughput: {result.throughput_fps:.1f} FPS")
            print(f"    VRAM: {result.vram_used_mb:.0f} MB (peak: {result.vram_peak_mb:.0f} MB)")

            results.append(result)

        # Cleanup
        del model
        del processor
        gc.collect()
        if device.startswith("cuda") and torch.cuda.is_available():
            torch.cuda.empty_cache()

    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback

        traceback.print_exc()
        results.append(
            BenchmarkResult(
                model_name=model_name,
                resolution=resolution,
                device=device,
                batch_size=1,
                latency_mean_ms=0,
                latency_std_ms=0,
                latency_min_ms=0,
                latency_max_ms=0,
                latency_p50_ms=0,
                latency_p95_ms=0,
                latency_p99_ms=0,
                error=str(e),
            )
        )

    return results


def generate_markdown_report(
    yolo_results: dict[str, list[BenchmarkResult]],
    yolo26_results: list[BenchmarkResult],
    gpu_info: dict[str, Any],
    resolutions: list[tuple[int, int]],
    batch_sizes: list[int],
) -> str:
    """Generate a comprehensive markdown benchmark report."""
    lines = [
        "# YOLO26 vs YOLO26 Benchmark Results",
        "",
        "> **Note:** This file is auto-generated by `scripts/benchmark_yolo26_latency.py`.",
        "> To refresh these results, run: `uv run python scripts/benchmark_yolo26_latency.py`",
        "",
        f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**GPU:** {gpu_info['name']}",
        f"**VRAM:** {gpu_info['memory_total_mb']} MiB",
        f"**CUDA Version:** {gpu_info['cuda_version']}",
        f"**Driver Version:** {gpu_info['driver_version']}",
        "",
        "## Executive Summary",
        "",
        "This benchmark compares YOLO26 variants (nano, small, medium) against YOLO26 for home security monitoring use cases.",
        "",
        "### Key Findings",
        "",
    ]

    # Find best single-image latency results
    all_results = []
    for model_results in yolo_results.values():
        all_results.extend([r for r in model_results if r.batch_size == 1 and r.error is None])
    all_results.extend([r for r in yolo26_results if r.batch_size == 1 and r.error is None])

    if all_results:
        # Group by resolution
        for resolution in resolutions:
            res_results = [r for r in all_results if r.resolution == resolution]
            if res_results:
                fastest = min(res_results, key=lambda x: x.latency_mean_ms)
                lines.append(
                    f"- **{resolution[0]}x{resolution[1]}:** Fastest model is **{fastest.model_name}** at {fastest.latency_mean_ms:.2f}ms ({1000 / fastest.latency_mean_ms:.1f} FPS)"
                )

    lines.extend(
        [
            "",
            "## Model Overview",
            "",
            "| Model | Parameters | Size | Architecture | Task |",
            "|-------|------------|------|--------------|------|",
        ]
    )

    # Add model info
    for model_name, results in yolo_results.items():
        if results and results[0].error is None:
            r = results[0]
            lines.append(
                f"| {model_name} | {r.parameters_m:.2f}M | {r.model_size_mb:.1f} MB | YOLO26 | Detection |"
            )

    if yolo26_results and yolo26_results[0].error is None:
        r = yolo26_results[0]
        lines.append(
            f"| yolo26-v2-r101vd | {r.parameters_m:.2f}M | {r.model_size_mb:.1f} MB | YOLO26 | Detection |"
        )

    # Latency comparison section
    lines.extend(
        [
            "",
            "## Latency Comparison (Single Image, Batch Size = 1)",
            "",
            "Lower is better. All values in milliseconds (ms).",
            "",
        ]
    )

    for resolution in resolutions:
        lines.extend(
            [
                f"### {resolution[0]}x{resolution[1]} Resolution",
                "",
                "| Model | Mean | Std | Min | Max | P50 | P95 | P99 |",
                "|-------|------|-----|-----|-----|-----|-----|-----|",
            ]
        )

        for model_name, results in yolo_results.items():
            batch1_results = [
                r for r in results if r.batch_size == 1 and r.resolution == resolution
            ]
            if batch1_results:
                r = batch1_results[0]
                if r.error:
                    lines.append(f"| {model_name} | ERROR | - | - | - | - | - | - |")
                else:
                    lines.append(
                        f"| {model_name} | {r.latency_mean_ms:.2f} | {r.latency_std_ms:.2f} | "
                        f"{r.latency_min_ms:.2f} | {r.latency_max_ms:.2f} | {r.latency_p50_ms:.2f} | "
                        f"{r.latency_p95_ms:.2f} | {r.latency_p99_ms:.2f} |"
                    )

        batch1_yolo26 = [
            r for r in yolo26_results if r.batch_size == 1 and r.resolution == resolution
        ]
        if batch1_yolo26:
            r = batch1_yolo26[0]
            if r.error:
                lines.append("| yolo26-v2-r101vd | ERROR | - | - | - | - | - | - |")
            else:
                lines.append(
                    f"| yolo26-v2-r101vd | {r.latency_mean_ms:.2f} | {r.latency_std_ms:.2f} | "
                    f"{r.latency_min_ms:.2f} | {r.latency_max_ms:.2f} | {r.latency_p50_ms:.2f} | "
                    f"{r.latency_p95_ms:.2f} | {r.latency_p99_ms:.2f} |"
                )

        lines.append("")

    # Component breakdown
    lines.extend(
        [
            "## Latency Breakdown (Batch Size = 1, 640x640)",
            "",
            "Shows preprocessing, inference, and postprocessing times.",
            "",
            "| Model | Preprocess (ms) | Inference (ms) | Postprocess (ms) | Total (ms) |",
            "|-------|-----------------|----------------|------------------|------------|",
        ]
    )

    for model_name, results in yolo_results.items():
        batch1_640 = [r for r in results if r.batch_size == 1 and r.resolution == (640, 640)]
        if batch1_640:
            r = batch1_640[0]
            if r.error is None:
                lines.append(
                    f"| {model_name} | {r.preprocess_mean_ms:.2f} | {r.inference_mean_ms:.2f} | "
                    f"{r.postprocess_mean_ms:.2f} | {r.latency_mean_ms:.2f} |"
                )

    batch1_yolo26_640 = [
        r for r in yolo26_results if r.batch_size == 1 and r.resolution == (640, 640)
    ]
    if batch1_yolo26_640:
        r = batch1_yolo26_640[0]
        if r.error is None:
            lines.append(
                f"| yolo26-v2-r101vd | {r.preprocess_mean_ms:.2f} | {r.inference_mean_ms:.2f} | "
                f"{r.postprocess_mean_ms:.2f} | {r.latency_mean_ms:.2f} |"
            )

    # Throughput comparison
    lines.extend(
        [
            "",
            "## Throughput Comparison (FPS)",
            "",
            "Higher is better. FPS = Frames Per Second.",
            "",
        ]
    )

    for resolution in resolutions:
        lines.extend(
            [
                f"### {resolution[0]}x{resolution[1]} Resolution",
                "",
                "| Model | Batch 1 | Batch 4 | Batch 8 | Batch 16 |",
                "|-------|---------|---------|---------|----------|",
            ]
        )

        for model_name, results in yolo_results.items():
            res_results = [r for r in results if r.resolution == resolution and r.error is None]
            if res_results:
                fps_by_batch = {r.batch_size: r.throughput_fps for r in res_results}
                b1 = f"{fps_by_batch.get(1, 0):.1f}" if 1 in fps_by_batch else "-"
                b4 = f"{fps_by_batch.get(4, 0):.1f}" if 4 in fps_by_batch else "-"
                b8 = f"{fps_by_batch.get(8, 0):.1f}" if 8 in fps_by_batch else "-"
                b16 = f"{fps_by_batch.get(16, 0):.1f}" if 16 in fps_by_batch else "-"
                lines.append(f"| {model_name} | {b1} | {b4} | {b8} | {b16} |")

        res_yolo26 = [r for r in yolo26_results if r.resolution == resolution and r.error is None]
        if res_yolo26:
            fps_by_batch = {r.batch_size: r.throughput_fps for r in res_yolo26}
            b1 = f"{fps_by_batch.get(1, 0):.1f}" if 1 in fps_by_batch else "-"
            b4 = f"{fps_by_batch.get(4, 0):.1f}" if 4 in fps_by_batch else "-"
            b8 = f"{fps_by_batch.get(8, 0):.1f}" if 8 in fps_by_batch else "-"
            b16 = f"{fps_by_batch.get(16, 0):.1f}" if 16 in fps_by_batch else "-"
            lines.append(f"| yolo26-v2-r101vd | {b1} | {b4} | {b8} | {b16} |")

        lines.append("")

    # VRAM usage
    lines.extend(
        [
            "## VRAM Usage",
            "",
            "GPU memory requirements for deployment planning.",
            "",
            "| Model | Resolution | Batch Size | VRAM Used (MB) | VRAM Peak (MB) |",
            "|-------|------------|------------|----------------|----------------|",
        ]
    )

    for model_name, results in yolo_results.items():
        for r in results:
            if r.error is None:
                lines.append(
                    f"| {model_name} | {r.resolution[0]}x{r.resolution[1]} | {r.batch_size} | "
                    f"{r.vram_used_mb:.0f} | {r.vram_peak_mb:.0f} |"
                )

    for r in yolo26_results:
        if r.error is None:
            lines.append(
                f"| yolo26-v2-r101vd | {r.resolution[0]}x{r.resolution[1]} | {r.batch_size} | "
                f"{r.vram_used_mb:.0f} | {r.vram_peak_mb:.0f} |"
            )

    # VRAM Requirements table for deployment planning
    lines.extend(
        [
            "",
            "## VRAM Requirements for Deployment",
            "",
            "Recommended VRAM allocation for different deployment scenarios:",
            "",
            "| Model | Single Camera (640x640) | Single Camera (1280x1280) | Multi-Camera (4x 640x640) |",
            "|-------|-------------------------|---------------------------|---------------------------|",
        ]
    )

    for model_name, results in yolo_results.items():
        single_640 = [
            r
            for r in results
            if r.resolution == (640, 640) and r.batch_size == 1 and r.error is None
        ]
        single_1280 = [
            r
            for r in results
            if r.resolution == (1280, 1280) and r.batch_size == 1 and r.error is None
        ]
        multi_640 = [
            r
            for r in results
            if r.resolution == (640, 640) and r.batch_size == 4 and r.error is None
        ]

        vram_640 = f"{single_640[0].vram_peak_mb:.0f} MB" if single_640 else "-"
        vram_1280 = f"{single_1280[0].vram_peak_mb:.0f} MB" if single_1280 else "-"
        vram_multi = f"{multi_640[0].vram_peak_mb:.0f} MB" if multi_640 else "-"

        lines.append(f"| {model_name} | {vram_640} | {vram_1280} | {vram_multi} |")

    single_640_yolo26 = [
        r
        for r in yolo26_results
        if r.resolution == (640, 640) and r.batch_size == 1 and r.error is None
    ]
    single_1280_yolo26 = [
        r
        for r in yolo26_results
        if r.resolution == (1280, 1280) and r.batch_size == 1 and r.error is None
    ]
    multi_640_yolo26 = [
        r
        for r in yolo26_results
        if r.resolution == (640, 640) and r.batch_size == 4 and r.error is None
    ]

    vram_640 = f"{single_640_yolo26[0].vram_peak_mb:.0f} MB" if single_640_yolo26 else "-"
    vram_1280 = f"{single_1280_yolo26[0].vram_peak_mb:.0f} MB" if single_1280_yolo26 else "-"
    vram_multi = f"{multi_640_yolo26[0].vram_peak_mb:.0f} MB" if multi_640_yolo26 else "-"
    lines.append(f"| yolo26-v2-r101vd | {vram_640} | {vram_1280} | {vram_multi} |")

    # Recommendations
    lines.extend(
        [
            "",
            "## Recommendations",
            "",
            "### For Real-Time Security Monitoring",
            "",
            "| Use Case | Recommended Model | Rationale |",
            "|----------|-------------------|-----------|",
            "| Low-power edge device | yolo26n | Lowest VRAM, fastest inference |",
            "| Standard security camera | yolo26s | Good balance of speed and accuracy |",
            "| High-resolution feeds | yolo26m | Better accuracy at higher resolutions |",
            "| Maximum accuracy | yolo26-v2-r101vd | Transformer architecture, best detection quality |",
            "",
            "### Latency Targets for Security Applications",
            "",
            "| Application | Target Latency | Recommended Configuration |",
            "|-------------|----------------|---------------------------|",
            "| Real-time alert (<100ms) | <50ms | yolo26n/s at 640x640 |",
            "| Near real-time (<500ms) | <200ms | yolo26m at 640x640 or yolo26s at 1280x1280 |",
            "| Batch processing | <1000ms | Any model, optimize for throughput with larger batches |",
            "",
            "## Benchmark Configuration",
            "",
            f"- **Warmup iterations:** {DEFAULT_WARMUP_ITERATIONS}",
            f"- **Benchmark iterations:** {DEFAULT_BENCHMARK_ITERATIONS}",
            f"- **Batch sizes tested:** {', '.join(map(str, batch_sizes))}",
            f"- **Resolutions tested:** {', '.join(f'{r[0]}x{r[1]}' for r in resolutions)}",
            "",
            "## Notes",
            "",
            "- All measurements taken on the same hardware under consistent conditions",
            "- VRAM measurements include model weights and inference buffers",
            "- Latency includes preprocessing, inference, and postprocessing",
            "- YOLO26 uses end-to-end NMS-free inference which reduces postprocessing overhead",
            "- YOLO26 uses SDPA attention when available for optimized inference",
            "",
        ]
    )

    return "\n".join(lines)


def main() -> None:
    """Run the benchmark."""
    parser = argparse.ArgumentParser(
        description="Benchmark YOLO26 vs YOLO26 latency and throughput"
    )
    parser.add_argument(
        "--models",
        type=str,
        default="yolo26n,yolo26s,yolo26m,yolo26",
        help="Comma-separated list of models to benchmark (default: yolo26n,yolo26s,yolo26m,yolo26)",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="cuda:0",
        help="Device to run benchmarks on (default: cuda:0)",
    )
    parser.add_argument(
        "--batch-sizes",
        type=str,
        default="1,4,8,16",
        help="Comma-separated list of batch sizes (default: 1,4,8,16)",
    )
    parser.add_argument(
        "--resolutions",
        type=str,
        default="640,1280",
        help="Comma-separated list of resolutions (default: 640,1280)",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=DEFAULT_WARMUP_ITERATIONS,
        help=f"Number of warmup iterations (default: {DEFAULT_WARMUP_ITERATIONS})",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=DEFAULT_BENCHMARK_ITERATIONS,
        help=f"Number of benchmark iterations (default: {DEFAULT_BENCHMARK_ITERATIONS})",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="docs/benchmarks/yolo26-vs-yolo26.md",
        help="Output file path for markdown report",
    )
    args = parser.parse_args()

    # Parse arguments
    models_to_run = [m.strip().lower() for m in args.models.split(",")]
    batch_sizes = [int(b.strip()) for b in args.batch_sizes.split(",")]
    resolutions = [(int(r.strip()), int(r.strip())) for r in args.resolutions.split(",")]

    print("=" * 60)
    print("YOLO26 vs YOLO26 Benchmark")
    print("=" * 60)
    print(f"Models: {', '.join(models_to_run)}")
    print(f"Device: {args.device}")
    print(f"Batch sizes: {batch_sizes}")
    print(f"Resolutions: {[f'{r[0]}x{r[1]}' for r in resolutions]}")
    print(f"Warmup iterations: {args.warmup}")
    print(f"Benchmark iterations: {args.iterations}")
    print()

    # Get GPU info
    gpu_info = get_gpu_info()
    print(f"GPU: {gpu_info['name']}")
    print(f"VRAM: {gpu_info['memory_total_mb']} MiB")
    print(f"CUDA: {gpu_info['cuda_version']}")

    # Check if CUDA is available
    try:
        import torch

        if args.device.startswith("cuda") and not torch.cuda.is_available():
            print("\nWARNING: CUDA requested but not available, falling back to CPU")
            args.device = "cpu"
    except ImportError:
        print("\nWARNING: PyTorch not available")

    # Run benchmarks
    yolo_results: dict[str, list[BenchmarkResult]] = {}
    yolo26_results: list[BenchmarkResult] = []

    # YOLO26 models
    yolo_models = {
        "yolo26n": YOLO26_MODEL_DIR / "yolo26n.pt",
        "yolo26s": YOLO26_MODEL_DIR / "yolo26s.pt",
        "yolo26m": YOLO26_MODEL_DIR / "yolo26m.pt",
    }

    for model_name, model_path in yolo_models.items():
        if model_name in models_to_run:
            if not model_path.exists():
                print(f"\nWARNING: {model_name} not found at {model_path}")
                continue

            all_results = []
            for resolution in resolutions:
                results = benchmark_yolo26_model(
                    model_path=model_path,
                    resolution=resolution,
                    batch_sizes=batch_sizes,
                    device=args.device,
                    warmup_iterations=args.warmup,
                    benchmark_iterations=args.iterations,
                )
                all_results.extend(results)

            yolo_results[model_name] = all_results

    # YOLO26
    if "yolo26" in models_to_run:
        if not YOLO26_MODEL_PATH.exists():
            print(f"\nWARNING: YOLO26 not found at {YOLO26_MODEL_PATH}")
        else:
            for resolution in resolutions:
                results = benchmark_yolo26_model(
                    model_path=YOLO26_MODEL_PATH,
                    resolution=resolution,
                    batch_sizes=batch_sizes,
                    device=args.device,
                    warmup_iterations=args.warmup,
                    benchmark_iterations=args.iterations,
                )
                yolo26_results.extend(results)

    # Generate report
    print("\n" + "=" * 60)
    print("Generating report...")
    print("=" * 60)

    report = generate_markdown_report(
        yolo_results=yolo_results,
        yolo26_results=yolo26_results,
        gpu_info=gpu_info,
        resolutions=resolutions,
        batch_sizes=batch_sizes,
    )

    # Write report
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report)
    print(f"\nReport written to: {output_path}")

    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    # Find best models
    all_single_image = []
    for model_name, results in yolo_results.items():
        all_single_image.extend(
            [(model_name, r) for r in results if r.batch_size == 1 and r.error is None]
        )
    all_single_image.extend(
        [("yolo26-v2-r101vd", r) for r in yolo26_results if r.batch_size == 1 and r.error is None]
    )

    if all_single_image:
        fastest = min(all_single_image, key=lambda x: x[1].latency_mean_ms)
        print(f"Fastest overall: {fastest[0]} at {fastest[1].latency_mean_ms:.2f}ms")

        lowest_vram = min(all_single_image, key=lambda x: x[1].vram_peak_mb)
        print(f"Lowest VRAM: {lowest_vram[0]} at {lowest_vram[1].vram_peak_mb:.0f}MB")


if __name__ == "__main__":
    main()
