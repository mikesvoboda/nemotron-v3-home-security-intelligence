#!/usr/bin/env python3
"""GPU benchmark for YOLO26 vs YOLO26 with all export formats.

This script benchmarks YOLO26 models in PyTorch, ONNX, and TensorRT formats,
comparing against YOLO26 baseline. It measures:
- Inference latency (ms) - mean, p50, p95, p99
- Throughput (FPS)
- GPU VRAM usage (MB)
- Warmup time

Requirements:
    Python 3.12 (ONNXRuntime doesn't support 3.14)
    pip install ultralytics torch torchvision onnxruntime-gpu transformers

Usage:
    # Full benchmark (all models, all formats)
    python scripts/benchmark_yolo26_gpu.py

    # Benchmark specific models
    python scripts/benchmark_yolo26_gpu.py --models yolo26n,yolo26s

    # Benchmark specific formats
    python scripts/benchmark_yolo26_gpu.py --formats pytorch,tensorrt

    # Export models first, then benchmark
    python scripts/benchmark_yolo26_gpu.py --export

    # Skip export and benchmark existing models
    python scripts/benchmark_yolo26_gpu.py --skip-export

Environment Variables:
    YOLO26_MODEL_PATH: YOLO26 model directory (default: /export/ai_models/model-zoo/yolo26)
    YOLO26_MODEL_PATH: YOLO26 model path (default: /export/ai_models/yolo26v2/yolo26_v2_r101vd)
"""

from __future__ import annotations

import argparse
import gc
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import torch
from PIL import Image

# =============================================================================
# Constants
# =============================================================================

DEFAULT_YOLO26_PATH = Path(
    os.environ.get("YOLO26_MODEL_PATH", "/export/ai_models/model-zoo/yolo26")
)
DEFAULT_YOLO26_PATH = Path(
    os.environ.get("YOLO26_MODEL_PATH", "/export/ai_models/yolo26v2/yolo26_v2_r101vd")
)
DEFAULT_EXPORT_PATH = DEFAULT_YOLO26_PATH / "exports"
DEFAULT_OUTPUT_PATH = Path(__file__).parent.parent / "docs/benchmarks/yolo26-vs-yolo26.md"

# Benchmark configuration
DEFAULT_WARMUP_ITERATIONS = 20
DEFAULT_BENCHMARK_ITERATIONS = 100
DEFAULT_INPUT_SIZE = 640
DEFAULT_BATCH_SIZE = 1  # Real-time inference


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class BenchmarkResult:
    """Benchmark result for a single model/format combination."""

    model_name: str
    format_name: str  # pytorch, onnx, tensorrt
    device: str
    input_size: int
    batch_size: int

    # Latency metrics (ms)
    latency_mean_ms: float = 0.0
    latency_std_ms: float = 0.0
    latency_min_ms: float = 0.0
    latency_max_ms: float = 0.0
    latency_p50_ms: float = 0.0
    latency_p95_ms: float = 0.0
    latency_p99_ms: float = 0.0

    # Throughput
    throughput_fps: float = 0.0

    # Memory usage
    vram_before_mb: float = 0.0
    vram_after_mb: float = 0.0
    vram_peak_mb: float = 0.0
    vram_model_mb: float = 0.0

    # Load/warmup time
    load_time_s: float = 0.0
    warmup_time_s: float = 0.0

    # Model info
    file_size_mb: float = 0.0
    parameters_m: float = 0.0

    # Error tracking
    error: str | None = None


@dataclass
class ExportResult:
    """Result of exporting a model to a format."""

    model_name: str
    format_name: str
    output_path: Path | None
    export_time_s: float = 0.0
    file_size_mb: float = 0.0
    success: bool = False
    error: str | None = None


# =============================================================================
# GPU Utilities
# =============================================================================


def get_gpu_memory_mb() -> tuple[float, float]:
    """Get current GPU memory usage in MB.

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
        # Get first GPU
        current = float(result.stdout.strip().split("\n")[0])

        # Get peak from PyTorch if available
        if torch.cuda.is_available():
            peak = torch.cuda.max_memory_allocated(0) / (1024 * 1024)
            return current, max(current, peak)

        return current, current
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
        return 0.0, 0.0


def get_gpu_info() -> dict[str, Any]:
    """Get GPU information."""
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,driver_version,compute_cap",
                "--format=csv,noheader",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        parts = [p.strip() for p in result.stdout.strip().split(",")]
        return {
            "name": parts[0] if len(parts) > 0 else "Unknown",
            "memory_total_mb": int(parts[1].replace(" MiB", "").strip()) if len(parts) > 1 else 0,
            "driver_version": parts[2] if len(parts) > 2 else "Unknown",
            "compute_capability": parts[3] if len(parts) > 3 else "Unknown",
        }
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError, IndexError):
        return {
            "name": "Unknown",
            "memory_total_mb": 0,
            "driver_version": "Unknown",
            "compute_capability": "Unknown",
        }


def clear_gpu_memory() -> None:
    """Clear GPU memory and run garbage collection."""
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
        torch.cuda.reset_peak_memory_stats()


def create_test_image(width: int = 640, height: int = 640) -> Image.Image:
    """Create a realistic test image for benchmarking."""
    np.random.seed(42)
    # Create image with some realistic variation
    data = np.random.randint(80, 180, (height, width, 3), dtype=np.uint8)
    # Add some rectangular regions (simulating objects)
    data[100:300, 150:400] = [180, 160, 140]
    data[350:500, 200:450] = [140, 180, 160]
    return Image.fromarray(data)


# =============================================================================
# Export Functions
# =============================================================================


def export_yolo26_onnx(
    model_path: Path,
    output_dir: Path,
    input_size: int = 640,
) -> ExportResult:
    """Export YOLO26 model to ONNX format."""
    from ultralytics import YOLO

    model_name = model_path.stem
    output_path = output_dir / f"{model_name}.onnx"

    print(f"  Exporting {model_name} to ONNX...")

    try:
        start_time = time.time()

        model = YOLO(str(model_path))
        model.export(
            format="onnx",
            imgsz=input_size,
            simplify=True,
            opset=17,
            dynamic=False,
        )

        export_time = time.time() - start_time

        # Move exported file to output directory
        exported_path = model_path.with_suffix(".onnx")
        if exported_path.exists():
            exported_path.rename(output_path)

        if output_path.exists():
            file_size_mb = output_path.stat().st_size / (1024 * 1024)
            return ExportResult(
                model_name=model_name,
                format_name="onnx",
                output_path=output_path,
                export_time_s=export_time,
                file_size_mb=file_size_mb,
                success=True,
            )
        else:
            return ExportResult(
                model_name=model_name,
                format_name="onnx",
                output_path=None,
                success=False,
                error="Export completed but output file not found",
            )

    except Exception as e:
        return ExportResult(
            model_name=model_name,
            format_name="onnx",
            output_path=None,
            success=False,
            error=str(e),
        )


def export_yolo26_tensorrt(
    model_path: Path,
    output_dir: Path,
    input_size: int = 640,
    half: bool = True,
) -> ExportResult:
    """Export YOLO26 model to TensorRT engine format."""
    from ultralytics import YOLO

    model_name = model_path.stem
    output_path = output_dir / f"{model_name}.engine"

    precision = "FP16" if half else "FP32"
    print(f"  Exporting {model_name} to TensorRT ({precision})...")

    try:
        if not torch.cuda.is_available():
            return ExportResult(
                model_name=model_name,
                format_name="tensorrt",
                output_path=None,
                success=False,
                error="CUDA not available for TensorRT export",
            )

        start_time = time.time()

        model = YOLO(str(model_path))
        model.export(
            format="engine",
            imgsz=input_size,
            half=half,
            device=0,
            dynamic=False,
            simplify=True,
        )

        export_time = time.time() - start_time

        # Move exported file to output directory
        exported_path = model_path.with_suffix(".engine")
        if exported_path.exists():
            exported_path.rename(output_path)

        if output_path.exists():
            file_size_mb = output_path.stat().st_size / (1024 * 1024)
            return ExportResult(
                model_name=model_name,
                format_name="tensorrt",
                output_path=output_path,
                export_time_s=export_time,
                file_size_mb=file_size_mb,
                success=True,
            )
        else:
            return ExportResult(
                model_name=model_name,
                format_name="tensorrt",
                output_path=None,
                success=False,
                error="Export completed but output file not found",
            )

    except Exception as e:
        return ExportResult(
            model_name=model_name,
            format_name="tensorrt",
            output_path=None,
            success=False,
            error=str(e),
        )


# =============================================================================
# Benchmark Functions
# =============================================================================


def benchmark_yolo26_pytorch(
    model_path: Path,
    input_size: int,
    warmup_iterations: int,
    benchmark_iterations: int,
    device: str = "cuda:0",
) -> BenchmarkResult:
    """Benchmark YOLO26 model in PyTorch format."""
    from ultralytics import YOLO

    model_name = model_path.stem
    result = BenchmarkResult(
        model_name=model_name,
        format_name="pytorch",
        device=device,
        input_size=input_size,
        batch_size=1,
    )

    try:
        clear_gpu_memory()
        vram_before, _ = get_gpu_memory_mb()
        result.vram_before_mb = vram_before

        # Load model
        load_start = time.time()
        model = YOLO(str(model_path))
        model.to(device)
        result.load_time_s = time.time() - load_start

        # Get model info
        result.file_size_mb = model_path.stat().st_size / (1024 * 1024)
        if hasattr(model.model, "parameters"):
            result.parameters_m = sum(p.numel() for p in model.model.parameters()) / 1e6

        # Create test image
        test_image = create_test_image(input_size, input_size)

        # Warmup
        print(f"  Warming up {model_name} (PyTorch)...")
        warmup_start = time.time()
        for _ in range(warmup_iterations):
            model(test_image, verbose=False)
        result.warmup_time_s = time.time() - warmup_start

        torch.cuda.synchronize()
        vram_after, vram_peak = get_gpu_memory_mb()
        result.vram_after_mb = vram_after
        result.vram_peak_mb = vram_peak
        result.vram_model_mb = vram_after - vram_before

        # Benchmark
        print(f"  Benchmarking {model_name} (PyTorch) - {benchmark_iterations} iterations...")
        latencies = []
        for _ in range(benchmark_iterations):
            torch.cuda.synchronize()
            start = time.perf_counter()
            model(test_image, verbose=False)
            torch.cuda.synchronize()
            latencies.append((time.perf_counter() - start) * 1000)

        # Calculate statistics
        latencies = np.array(latencies)
        result.latency_mean_ms = float(np.mean(latencies))
        result.latency_std_ms = float(np.std(latencies))
        result.latency_min_ms = float(np.min(latencies))
        result.latency_max_ms = float(np.max(latencies))
        result.latency_p50_ms = float(np.percentile(latencies, 50))
        result.latency_p95_ms = float(np.percentile(latencies, 95))
        result.latency_p99_ms = float(np.percentile(latencies, 99))
        result.throughput_fps = 1000.0 / result.latency_mean_ms

        del model
        clear_gpu_memory()

    except Exception as e:
        result.error = str(e)

    return result


def benchmark_yolo26_onnx(
    onnx_path: Path,
    input_size: int,
    warmup_iterations: int,
    benchmark_iterations: int,
    use_tensorrt_ep: bool = False,
) -> BenchmarkResult:
    """Benchmark YOLO26 model in ONNX format with ONNX Runtime."""
    import onnxruntime as ort

    model_name = onnx_path.stem
    ep_name = "TensorRT-EP" if use_tensorrt_ep else "CUDA-EP"
    result = BenchmarkResult(
        model_name=model_name,
        format_name=f"onnx-{ep_name.lower()}",
        device="cuda:0",
        input_size=input_size,
        batch_size=1,
    )

    try:
        clear_gpu_memory()
        vram_before, _ = get_gpu_memory_mb()
        result.vram_before_mb = vram_before

        # Configure execution providers
        if use_tensorrt_ep and "TensorrtExecutionProvider" in ort.get_available_providers():
            providers = [
                (
                    "TensorrtExecutionProvider",
                    {
                        "device_id": 0,
                        "trt_max_workspace_size": 2 * 1024 * 1024 * 1024,
                        "trt_fp16_enable": True,
                    },
                ),
                ("CUDAExecutionProvider", {"device_id": 0}),
                "CPUExecutionProvider",
            ]
        else:
            providers = [
                ("CUDAExecutionProvider", {"device_id": 0}),
                "CPUExecutionProvider",
            ]

        # Load model
        load_start = time.time()
        session = ort.InferenceSession(str(onnx_path), providers=providers)
        result.load_time_s = time.time() - load_start

        result.file_size_mb = onnx_path.stat().st_size / (1024 * 1024)

        # Get input/output info
        input_name = session.get_inputs()[0].name
        input_shape = session.get_inputs()[0].shape

        # Create test input (NCHW format)
        np.random.seed(42)
        test_input = np.random.rand(1, 3, input_size, input_size).astype(np.float32)

        # Warmup
        print(f"  Warming up {model_name} ({ep_name})...")
        warmup_start = time.time()
        for _ in range(warmup_iterations):
            session.run(None, {input_name: test_input})
        result.warmup_time_s = time.time() - warmup_start

        if torch.cuda.is_available():
            torch.cuda.synchronize()
        vram_after, vram_peak = get_gpu_memory_mb()
        result.vram_after_mb = vram_after
        result.vram_peak_mb = vram_peak
        result.vram_model_mb = vram_after - vram_before

        # Benchmark
        print(f"  Benchmarking {model_name} ({ep_name}) - {benchmark_iterations} iterations...")
        latencies = []
        for _ in range(benchmark_iterations):
            if torch.cuda.is_available():
                torch.cuda.synchronize()
            start = time.perf_counter()
            session.run(None, {input_name: test_input})
            if torch.cuda.is_available():
                torch.cuda.synchronize()
            latencies.append((time.perf_counter() - start) * 1000)

        # Calculate statistics
        latencies = np.array(latencies)
        result.latency_mean_ms = float(np.mean(latencies))
        result.latency_std_ms = float(np.std(latencies))
        result.latency_min_ms = float(np.min(latencies))
        result.latency_max_ms = float(np.max(latencies))
        result.latency_p50_ms = float(np.percentile(latencies, 50))
        result.latency_p95_ms = float(np.percentile(latencies, 95))
        result.latency_p99_ms = float(np.percentile(latencies, 99))
        result.throughput_fps = 1000.0 / result.latency_mean_ms

        del session
        clear_gpu_memory()

    except Exception as e:
        result.error = str(e)

    return result


def benchmark_yolo26_tensorrt(
    engine_path: Path,
    input_size: int,
    warmup_iterations: int,
    benchmark_iterations: int,
) -> BenchmarkResult:
    """Benchmark YOLO26 model in TensorRT engine format via Ultralytics."""
    from ultralytics import YOLO

    model_name = engine_path.stem
    result = BenchmarkResult(
        model_name=model_name,
        format_name="tensorrt",
        device="cuda:0",
        input_size=input_size,
        batch_size=1,
    )

    try:
        clear_gpu_memory()
        vram_before, _ = get_gpu_memory_mb()
        result.vram_before_mb = vram_before

        # Load model
        print(f"  Loading TensorRT engine {model_name}...")
        load_start = time.time()
        model = YOLO(str(engine_path))
        result.load_time_s = time.time() - load_start

        result.file_size_mb = engine_path.stat().st_size / (1024 * 1024)

        # Create test image
        test_image = create_test_image(input_size, input_size)

        # Warmup
        print(f"  Warming up {model_name} (TensorRT)...")
        warmup_start = time.time()
        for _ in range(warmup_iterations):
            model(test_image, verbose=False)
        result.warmup_time_s = time.time() - warmup_start

        torch.cuda.synchronize()
        vram_after, vram_peak = get_gpu_memory_mb()
        result.vram_after_mb = vram_after
        result.vram_peak_mb = vram_peak
        result.vram_model_mb = vram_after - vram_before

        # Benchmark
        print(f"  Benchmarking {model_name} (TensorRT) - {benchmark_iterations} iterations...")
        latencies = []
        for _ in range(benchmark_iterations):
            torch.cuda.synchronize()
            start = time.perf_counter()
            model(test_image, verbose=False)
            torch.cuda.synchronize()
            latencies.append((time.perf_counter() - start) * 1000)

        # Calculate statistics
        latencies = np.array(latencies)
        result.latency_mean_ms = float(np.mean(latencies))
        result.latency_std_ms = float(np.std(latencies))
        result.latency_min_ms = float(np.min(latencies))
        result.latency_max_ms = float(np.max(latencies))
        result.latency_p50_ms = float(np.percentile(latencies, 50))
        result.latency_p95_ms = float(np.percentile(latencies, 95))
        result.latency_p99_ms = float(np.percentile(latencies, 99))
        result.throughput_fps = 1000.0 / result.latency_mean_ms

        del model
        clear_gpu_memory()

    except Exception as e:
        result.error = str(e)

    return result


def benchmark_yolo26(
    model_path: Path,
    input_size: int,
    warmup_iterations: int,
    benchmark_iterations: int,
    device: str = "cuda:0",
) -> BenchmarkResult:
    """Benchmark YOLO26 model."""
    from transformers import AutoImageProcessor, AutoModelForObjectDetection

    result = BenchmarkResult(
        model_name="YOLO26",
        format_name="pytorch",
        device=device,
        input_size=input_size,
        batch_size=1,
    )

    try:
        clear_gpu_memory()
        vram_before, _ = get_gpu_memory_mb()
        result.vram_before_mb = vram_before

        # Load model
        print("  Loading YOLO26...")
        load_start = time.time()
        processor = AutoImageProcessor.from_pretrained(str(model_path))
        model = AutoModelForObjectDetection.from_pretrained(str(model_path))
        model = model.to(device)
        model.eval()
        result.load_time_s = time.time() - load_start

        # Get model info
        result.parameters_m = sum(p.numel() for p in model.parameters()) / 1e6

        # Create test image
        test_image = create_test_image(input_size, input_size)

        # Warmup
        print("  Warming up YOLO26 (PyTorch)...")
        warmup_start = time.time()
        for _ in range(warmup_iterations):
            inputs = processor(images=test_image, return_tensors="pt")
            inputs = {k: v.to(device) for k, v in inputs.items()}
            with torch.inference_mode():
                model(**inputs)
        result.warmup_time_s = time.time() - warmup_start

        torch.cuda.synchronize()
        vram_after, vram_peak = get_gpu_memory_mb()
        result.vram_after_mb = vram_after
        result.vram_peak_mb = vram_peak
        result.vram_model_mb = vram_after - vram_before

        # Benchmark
        print(f"  Benchmarking YOLO26 (PyTorch) - {benchmark_iterations} iterations...")
        latencies = []
        for _ in range(benchmark_iterations):
            inputs = processor(images=test_image, return_tensors="pt")
            inputs = {k: v.to(device) for k, v in inputs.items()}
            torch.cuda.synchronize()
            start = time.perf_counter()
            with torch.inference_mode():
                model(**inputs)
            torch.cuda.synchronize()
            latencies.append((time.perf_counter() - start) * 1000)

        # Calculate statistics
        latencies = np.array(latencies)
        result.latency_mean_ms = float(np.mean(latencies))
        result.latency_std_ms = float(np.std(latencies))
        result.latency_min_ms = float(np.min(latencies))
        result.latency_max_ms = float(np.max(latencies))
        result.latency_p50_ms = float(np.percentile(latencies, 50))
        result.latency_p95_ms = float(np.percentile(latencies, 95))
        result.latency_p99_ms = float(np.percentile(latencies, 99))
        result.throughput_fps = 1000.0 / result.latency_mean_ms

        del model, processor
        clear_gpu_memory()

    except Exception as e:
        result.error = str(e)

    return result


# =============================================================================
# Report Generation
# =============================================================================


def generate_gpu_benchmark_report(
    results: list[BenchmarkResult],
    export_results: list[ExportResult],
    gpu_info: dict[str, Any],
) -> str:
    """Generate markdown report for GPU benchmarks."""
    lines = [
        "# YOLO26 vs YOLO26 GPU Benchmark Results",
        "",
        "> **Note:** This file is auto-generated by `scripts/benchmark_yolo26_gpu.py`.",
        "> To refresh results: `python scripts/benchmark_yolo26_gpu.py`",
        "",
        f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**GPU:** {gpu_info.get('name', 'Unknown')}",
        f"**VRAM:** {gpu_info.get('memory_total_mb', 0)} MB",
        f"**Driver:** {gpu_info.get('driver_version', 'Unknown')}",
        f"**CUDA:** {torch.version.cuda if torch.cuda.is_available() else 'N/A'}",
        f"**PyTorch:** {torch.__version__}",
        "",
    ]

    # Export results section
    if export_results:
        lines.extend(
            [
                "## Export Results",
                "",
                "| Model | Format | Status | Export Time | File Size |",
                "|-------|--------|--------|-------------|-----------|",
            ]
        )
        for exp in export_results:
            status = "SUCCESS" if exp.success else f"FAILED: {exp.error}"
            exp_time = f"{exp.export_time_s:.1f}s" if exp.success else "-"
            file_size = f"{exp.file_size_mb:.2f} MB" if exp.success else "-"
            lines.append(
                f"| {exp.model_name} | {exp.format_name.upper()} | {status} | {exp_time} | {file_size} |"
            )
        lines.append("")

    # Filter successful results
    successful_results = [r for r in results if r.error is None]
    failed_results = [r for r in results if r.error is not None]

    if successful_results:
        # Summary table
        lines.extend(
            [
                "## Benchmark Summary",
                "",
                "| Model | Format | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) | FPS | VRAM (MB) |",
                "|-------|--------|-----------|----------|----------|----------|-----|-----------|",
            ]
        )

        # Sort by latency
        for r in sorted(successful_results, key=lambda x: x.latency_mean_ms):
            lines.append(
                f"| {r.model_name} | {r.format_name} | {r.latency_mean_ms:.2f} | "
                f"{r.latency_p50_ms:.2f} | {r.latency_p95_ms:.2f} | {r.latency_p99_ms:.2f} | "
                f"{r.throughput_fps:.1f} | {r.vram_model_mb:.0f} |"
            )
        lines.append("")

        # Detailed results by model
        lines.extend(
            [
                "## Detailed Results",
                "",
            ]
        )

        # Group by model
        models = {}
        for r in successful_results:
            if r.model_name not in models:
                models[r.model_name] = []
            models[r.model_name].append(r)

        for model_name, model_results in models.items():
            lines.extend(
                [
                    f"### {model_name}",
                    "",
                    "| Format | Mean | Std | Min | Max | P50 | P95 | P99 | FPS | VRAM | Load Time | Warmup |",
                    "|--------|------|-----|-----|-----|-----|-----|-----|-----|------|-----------|--------|",
                ]
            )
            for r in sorted(model_results, key=lambda x: x.latency_mean_ms):
                lines.append(
                    f"| {r.format_name} | {r.latency_mean_ms:.2f}ms | {r.latency_std_ms:.2f}ms | "
                    f"{r.latency_min_ms:.2f}ms | {r.latency_max_ms:.2f}ms | {r.latency_p50_ms:.2f}ms | "
                    f"{r.latency_p95_ms:.2f}ms | {r.latency_p99_ms:.2f}ms | {r.throughput_fps:.1f} | "
                    f"{r.vram_model_mb:.0f}MB | {r.load_time_s:.2f}s | {r.warmup_time_s:.2f}s |"
                )
            lines.append("")

        # Speedup analysis
        lines.extend(
            [
                "## Speedup Analysis",
                "",
            ]
        )

        # Find baseline (YOLO26 or YOLO26N PyTorch)
        baseline = None
        for r in successful_results:
            if r.model_name == "YOLO26" and r.format_name == "pytorch":
                baseline = r
                break
        if baseline is None:
            for r in successful_results:
                if r.model_name == "yolo26n" and r.format_name == "pytorch":
                    baseline = r
                    break

        if baseline:
            lines.extend(
                [
                    f"**Baseline:** {baseline.model_name} ({baseline.format_name}) @ {baseline.latency_mean_ms:.2f}ms",
                    "",
                    "| Model | Format | Speedup vs Baseline | Latency Reduction |",
                    "|-------|--------|---------------------|-------------------|",
                ]
            )
            for r in sorted(successful_results, key=lambda x: x.latency_mean_ms):
                if r != baseline:
                    speedup = baseline.latency_mean_ms / r.latency_mean_ms
                    reduction = (1 - r.latency_mean_ms / baseline.latency_mean_ms) * 100
                    lines.append(
                        f"| {r.model_name} | {r.format_name} | {speedup:.2f}x | {reduction:.1f}% |"
                    )
            lines.append("")

        # TensorRT vs PyTorch comparison
        tensorrt_results = [r for r in successful_results if r.format_name == "tensorrt"]
        pytorch_results = [
            r for r in successful_results if r.format_name == "pytorch" and r.model_name != "YOLO26"
        ]

        if tensorrt_results and pytorch_results:
            lines.extend(
                [
                    "## TensorRT vs PyTorch Speedup",
                    "",
                    "| Model | PyTorch (ms) | TensorRT (ms) | Speedup | VRAM Savings |",
                    "|-------|--------------|---------------|---------|--------------|",
                ]
            )
            for trt in tensorrt_results:
                # Find matching PyTorch result
                pt = next((r for r in pytorch_results if r.model_name == trt.model_name), None)
                if pt:
                    speedup = pt.latency_mean_ms / trt.latency_mean_ms
                    vram_savings = pt.vram_model_mb - trt.vram_model_mb
                    lines.append(
                        f"| {trt.model_name} | {pt.latency_mean_ms:.2f} | {trt.latency_mean_ms:.2f} | "
                        f"{speedup:.2f}x | {vram_savings:.0f} MB |"
                    )
            lines.append("")

    # Failed benchmarks
    if failed_results:
        lines.extend(
            [
                "## Failed Benchmarks",
                "",
                "| Model | Format | Error |",
                "|-------|--------|-------|",
            ]
        )
        for r in failed_results:
            lines.append(f"| {r.model_name} | {r.format_name} | {r.error} |")
        lines.append("")

    # Recommendations
    lines.extend(
        [
            "## Recommendations",
            "",
        ]
    )

    if successful_results:
        # Find best performers
        fastest = min(successful_results, key=lambda x: x.latency_mean_ms)
        lowest_vram = min(
            successful_results,
            key=lambda x: x.vram_model_mb if x.vram_model_mb > 0 else float("inf"),
        )
        best_fps = max(successful_results, key=lambda x: x.throughput_fps)

        lines.extend(
            [
                f"- **Fastest Inference:** {fastest.model_name} ({fastest.format_name}) @ {fastest.latency_mean_ms:.2f}ms ({fastest.throughput_fps:.0f} FPS)",
                f"- **Lowest VRAM:** {lowest_vram.model_name} ({lowest_vram.format_name}) @ {lowest_vram.vram_model_mb:.0f} MB",
                f"- **Best Throughput:** {best_fps.model_name} ({best_fps.format_name}) @ {best_fps.throughput_fps:.0f} FPS",
                "",
                "### Production Deployment",
                "",
            ]
        )

        # Check if TensorRT is available
        has_tensorrt = any(r.format_name == "tensorrt" for r in successful_results)
        if has_tensorrt:
            trt_fastest = min(
                [r for r in successful_results if r.format_name == "tensorrt"],
                key=lambda x: x.latency_mean_ms,
            )
            lines.extend(
                [
                    f"**Recommended:** {trt_fastest.model_name} TensorRT engine",
                    "",
                    "TensorRT provides the best inference speed on NVIDIA GPUs. Use FP16 for optimal performance.",
                    "",
                    "```yaml",
                    "# docker-compose configuration",
                    "ai-detector:",
                    "  environment:",
                    f"    DETECTOR_MODEL: /models/yolo26/exports/{trt_fastest.model_name}.engine",
                    "    DETECTOR_DEVICE: cuda:0",
                    "```",
                ]
            )
        else:
            lines.extend(
                [
                    "**Note:** TensorRT exports not available. Consider exporting models to TensorRT for",
                    "optimal GPU performance.",
                ]
            )
    else:
        lines.append("No successful benchmarks to analyze.")

    lines.append("")
    return "\n".join(lines)


# =============================================================================
# Main Entry Point
# =============================================================================


def main() -> None:
    """Run GPU benchmarks for YOLO26 vs YOLO26."""
    parser = argparse.ArgumentParser(
        description="GPU benchmark for YOLO26 vs YOLO26 with all export formats",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--models",
        type=str,
        default="yolo26n,yolo26s,yolo26m,yolo26",
        help="Comma-separated list of models to benchmark (default: all)",
    )
    parser.add_argument(
        "--formats",
        type=str,
        default="pytorch,onnx,tensorrt",
        help="Comma-separated list of formats to benchmark (default: all)",
    )
    parser.add_argument(
        "--export",
        action="store_true",
        help="Export models before benchmarking",
    )
    parser.add_argument(
        "--skip-export",
        action="store_true",
        help="Skip export and use existing files",
    )
    parser.add_argument(
        "--input-size",
        type=int,
        default=DEFAULT_INPUT_SIZE,
        help=f"Input image size (default: {DEFAULT_INPUT_SIZE})",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=DEFAULT_WARMUP_ITERATIONS,
        help=f"Warmup iterations (default: {DEFAULT_WARMUP_ITERATIONS})",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=DEFAULT_BENCHMARK_ITERATIONS,
        help=f"Benchmark iterations (default: {DEFAULT_BENCHMARK_ITERATIONS})",
    )
    parser.add_argument(
        "--yolo-path",
        type=Path,
        default=DEFAULT_YOLO26_PATH,
        help="Path to YOLO26 models directory",
    )
    parser.add_argument(
        "--yolo26-path",
        type=Path,
        default=DEFAULT_YOLO26_PATH,
        help="Path to YOLO26 model",
    )
    parser.add_argument(
        "--export-path",
        type=Path,
        default=DEFAULT_EXPORT_PATH,
        help="Path for exported models",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Output path for markdown report",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="cuda:0",
        help="Device to run benchmarks on (default: cuda:0)",
    )

    args = parser.parse_args()

    # Check CUDA availability
    if not torch.cuda.is_available():
        print("ERROR: CUDA is not available. This script requires a GPU.")
        sys.exit(1)

    # Parse arguments
    model_names = [m.strip().lower() for m in args.models.split(",")]
    format_names = [f.strip().lower() for f in args.formats.split(",")]

    # Ensure export directory exists
    args.export_path.mkdir(parents=True, exist_ok=True)

    # Get GPU info
    gpu_info = get_gpu_info()

    print("=" * 70)
    print("YOLO26 vs YOLO26 GPU Benchmark")
    print("=" * 70)
    print(f"GPU: {gpu_info.get('name', 'Unknown')}")
    print(f"VRAM: {gpu_info.get('memory_total_mb', 0)} MB")
    print(f"PyTorch: {torch.__version__}")
    print(f"CUDA: {torch.version.cuda}")
    print(f"Models: {model_names}")
    print(f"Formats: {format_names}")
    print(f"Input size: {args.input_size}x{args.input_size}")
    print(f"Warmup: {args.warmup} iterations")
    print(f"Benchmark: {args.iterations} iterations")
    print()

    # Export models if requested
    export_results: list[ExportResult] = []

    if args.export and not args.skip_export:
        print("=" * 70)
        print("Exporting Models")
        print("=" * 70)

        for model_name in model_names:
            if model_name.startswith("yolo26"):
                variant = model_name.replace("yolo26", "") or "n"
                model_path = args.yolo_path / f"yolo26{variant}.pt"

                if not model_path.exists():
                    print(f"  WARNING: {model_path} not found, skipping export")
                    continue

                # Export to ONNX
                if "onnx" in format_names:
                    result = export_yolo26_onnx(model_path, args.export_path, args.input_size)
                    export_results.append(result)
                    if result.success:
                        print(
                            f"    ONNX: {result.file_size_mb:.2f} MB in {result.export_time_s:.1f}s"
                        )
                    else:
                        print(f"    ONNX: FAILED - {result.error}")

                # Export to TensorRT
                if "tensorrt" in format_names:
                    result = export_yolo26_tensorrt(
                        model_path, args.export_path, args.input_size, half=True
                    )
                    export_results.append(result)
                    if result.success:
                        print(
                            f"    TensorRT: {result.file_size_mb:.2f} MB in {result.export_time_s:.1f}s"
                        )
                    else:
                        print(f"    TensorRT: FAILED - {result.error}")

        print()

    # Run benchmarks
    print("=" * 70)
    print("Running Benchmarks")
    print("=" * 70)

    benchmark_results: list[BenchmarkResult] = []

    for model_name in model_names:
        print(f"\n{model_name.upper()}")
        print("-" * 40)

        if model_name == "yolo26":
            # YOLO26 benchmark (PyTorch only)
            if "pytorch" in format_names:
                result = benchmark_yolo26(
                    args.yolo26_path,
                    args.input_size,
                    args.warmup,
                    args.iterations,
                    args.device,
                )
                benchmark_results.append(result)
                if result.error:
                    print(f"  PyTorch: FAILED - {result.error}")
                else:
                    print(
                        f"  PyTorch: {result.latency_mean_ms:.2f}ms ({result.throughput_fps:.0f} FPS), VRAM: {result.vram_model_mb:.0f}MB"
                    )

        elif model_name.startswith("yolo26"):
            variant = model_name.replace("yolo26", "") or "n"
            model_path = args.yolo_path / f"yolo26{variant}.pt"

            if not model_path.exists():
                print(f"  WARNING: {model_path} not found, skipping")
                continue

            # PyTorch benchmark
            if "pytorch" in format_names:
                result = benchmark_yolo26_pytorch(
                    model_path,
                    args.input_size,
                    args.warmup,
                    args.iterations,
                    args.device,
                )
                benchmark_results.append(result)
                if result.error:
                    print(f"  PyTorch: FAILED - {result.error}")
                else:
                    print(
                        f"  PyTorch: {result.latency_mean_ms:.2f}ms ({result.throughput_fps:.0f} FPS), VRAM: {result.vram_model_mb:.0f}MB"
                    )

            # ONNX benchmark
            if "onnx" in format_names:
                onnx_path = args.export_path / f"yolo26{variant}.onnx"
                if onnx_path.exists():
                    # CUDA EP
                    result = benchmark_yolo26_onnx(
                        onnx_path,
                        args.input_size,
                        args.warmup,
                        args.iterations,
                        use_tensorrt_ep=False,
                    )
                    benchmark_results.append(result)
                    if result.error:
                        print(f"  ONNX-CUDA: FAILED - {result.error}")
                    else:
                        print(
                            f"  ONNX-CUDA: {result.latency_mean_ms:.2f}ms ({result.throughput_fps:.0f} FPS), VRAM: {result.vram_model_mb:.0f}MB"
                        )

                    # TensorRT EP (if available)
                    import onnxruntime as ort

                    if "TensorrtExecutionProvider" in ort.get_available_providers():
                        result = benchmark_yolo26_onnx(
                            onnx_path,
                            args.input_size,
                            args.warmup,
                            args.iterations,
                            use_tensorrt_ep=True,
                        )
                        benchmark_results.append(result)
                        if result.error:
                            print(f"  ONNX-TRT: FAILED - {result.error}")
                        else:
                            print(
                                f"  ONNX-TRT: {result.latency_mean_ms:.2f}ms ({result.throughput_fps:.0f} FPS), VRAM: {result.vram_model_mb:.0f}MB"
                            )
                else:
                    print(f"  ONNX: SKIPPED - {onnx_path} not found")

            # TensorRT benchmark
            if "tensorrt" in format_names:
                engine_path = args.export_path / f"yolo26{variant}.engine"
                if engine_path.exists():
                    result = benchmark_yolo26_tensorrt(
                        engine_path,
                        args.input_size,
                        args.warmup,
                        args.iterations,
                    )
                    benchmark_results.append(result)
                    if result.error:
                        print(f"  TensorRT: FAILED - {result.error}")
                    else:
                        print(
                            f"  TensorRT: {result.latency_mean_ms:.2f}ms ({result.throughput_fps:.0f} FPS), VRAM: {result.vram_model_mb:.0f}MB"
                        )
                else:
                    print(f"  TensorRT: SKIPPED - {engine_path} not found")

    # Generate report
    print("\n" + "=" * 70)
    print("Generating Report")
    print("=" * 70)

    report = generate_gpu_benchmark_report(benchmark_results, export_results, gpu_info)

    # Write report
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report)
    print(f"Report written to: {args.output}")

    # Print summary
    print("\n" + "=" * 70)
    print("BENCHMARK SUMMARY")
    print("=" * 70)

    successful = [r for r in benchmark_results if r.error is None]
    if successful:
        print(
            "\n{:<20} {:<15} {:>10} {:>10} {:>10}".format(
                "Model", "Format", "Mean (ms)", "FPS", "VRAM (MB)"
            )
        )
        print("-" * 70)
        for r in sorted(successful, key=lambda x: x.latency_mean_ms):
            print(
                f"{r.model_name:<20} {r.format_name:<15} {r.latency_mean_ms:>10.2f} {r.throughput_fps:>10.0f} {r.vram_model_mb:>10.0f}"
            )

        # Find best performer
        fastest = min(successful, key=lambda x: x.latency_mean_ms)
        print(
            f"\nFastest: {fastest.model_name} ({fastest.format_name}) @ {fastest.latency_mean_ms:.2f}ms ({fastest.throughput_fps:.0f} FPS)"
        )

    print("\nDone!")


if __name__ == "__main__":
    main()
