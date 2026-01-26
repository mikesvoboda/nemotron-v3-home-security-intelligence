#!/usr/bin/env python3
"""GPU benchmark for YOLO26 with native TensorRT support (container version).

This script is designed to run inside the yolo26-benchmark container with proper
TensorRT support. It exports YOLO26 models to TensorRT FP16 engines and benchmarks
all formats for comparison against YOLO26.

Requirements (provided by container):
    - Python 3.12
    - TensorRT 10.x
    - PyTorch 2.5+ with CUDA
    - ultralytics 8.3+
    - onnxruntime-gpu 1.19+
    - transformers 4.45+

Usage (inside container):
    # Full benchmark with TensorRT export
    python3 /scripts/benchmark_yolo26_container.py --export

    # Benchmark existing exports only
    python3 /scripts/benchmark_yolo26_container.py --skip-export

    # Export only (no benchmark)
    python3 /scripts/benchmark_yolo26_container.py --export-only

Environment Variables:
    YOLO26_MODEL_PATH: YOLO26 model directory (default: /models/yolo26)
    YOLO26_MODEL_PATH: YOLO26 model path (default: /models/yolo26v2/yolo26_v2_r101vd)
    EXPORT_PATH: Directory for TensorRT/ONNX exports (default: /models/yolo26/exports)
    BENCHMARK_OUTPUT: Output path for markdown report (default: /benchmarks/yolo26-vs-yolo26.md)
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

DEFAULT_YOLO26_PATH = Path(os.environ.get("YOLO26_MODEL_PATH", "/models/yolo26"))
DEFAULT_YOLO26_PATH = Path(
    os.environ.get("YOLO26_MODEL_PATH", "/models/yolo26v2/yolo26_v2_r101vd")
)
DEFAULT_EXPORT_PATH = Path(os.environ.get("EXPORT_PATH", "/models/yolo26/exports"))
DEFAULT_OUTPUT_PATH = Path(os.environ.get("BENCHMARK_OUTPUT", "/benchmarks/yolo26-vs-yolo26.md"))

# Benchmark configuration
WARMUP_ITERATIONS = 50  # More warmup for TensorRT
BENCHMARK_ITERATIONS = 200  # More iterations for stable results
INPUT_SIZE = 640
BATCH_SIZE = 1

# Model variants to benchmark
YOLO26_VARIANTS = ["yolo26n", "yolo26s", "yolo26m"]


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class BenchmarkResult:
    """Benchmark result for a single model/format combination."""

    model_name: str
    format_name: str
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
    vram_model_mb: float = 0.0

    # Load/warmup time
    load_time_s: float = 0.0
    warmup_time_s: float = 0.0

    # Model info
    file_size_mb: float = 0.0

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


def get_gpu_memory_mb() -> float:
    """Get current GPU memory usage in MB.

    Uses PyTorch's CUDA memory tracking for more accurate measurements
    during benchmarking.
    """
    if torch.cuda.is_available():
        # Use PyTorch's memory tracking for better accuracy
        return torch.cuda.memory_allocated(0) / (1024 * 1024)

    # Fallback to nvidia-smi
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            check=True,
        )
        return float(result.stdout.strip().split("\n")[0])
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
        return 0.0


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
            "memory_total_mb": (int(parts[1].replace(" MiB", "").strip()) if len(parts) > 1 else 0),
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


def get_tensorrt_version() -> str:
    """Get TensorRT version."""
    try:
        import tensorrt as trt

        return trt.__version__
    except ImportError:
        return "Not installed"


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

    print(f"  [ONNX] Exporting {model_name}...")

    try:
        start_time = time.time()

        model = YOLO(str(model_path))
        exported = model.export(
            format="onnx",
            imgsz=input_size,
            simplify=True,
            opset=17,
            dynamic=False,
        )

        export_time = time.time() - start_time

        # Move exported file to output directory
        exported_path = Path(exported)
        if exported_path.exists() and exported_path != output_path:
            # Copy to output directory
            import shutil

            shutil.copy2(exported_path, output_path)

        if output_path.exists():
            file_size_mb = output_path.stat().st_size / (1024 * 1024)
            print(f"         SUCCESS: {file_size_mb:.2f} MB in {export_time:.1f}s")
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
        print(f"         FAILED: {e}")
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
    """Export YOLO26 model to TensorRT engine format (FP16)."""
    from ultralytics import YOLO

    model_name = model_path.stem
    precision = "fp16" if half else "fp32"
    output_path = output_dir / f"{model_name}_{precision}.engine"

    print(f"  [TensorRT {precision.upper()}] Exporting {model_name}...")

    try:
        if not torch.cuda.is_available():
            return ExportResult(
                model_name=model_name,
                format_name=f"tensorrt-{precision}",
                output_path=None,
                success=False,
                error="CUDA not available for TensorRT export",
            )

        start_time = time.time()

        model = YOLO(str(model_path))
        exported = model.export(
            format="engine",
            imgsz=input_size,
            half=half,
            device=0,
            dynamic=False,
            simplify=True,
            workspace=4,  # 4GB workspace for TensorRT optimizer
        )

        export_time = time.time() - start_time

        # Move exported file to output directory
        exported_path = Path(exported)
        if exported_path.exists() and exported_path != output_path:
            import shutil

            shutil.copy2(exported_path, output_path)

        if output_path.exists():
            file_size_mb = output_path.stat().st_size / (1024 * 1024)
            print(f"         SUCCESS: {file_size_mb:.2f} MB in {export_time:.1f}s")
            return ExportResult(
                model_name=model_name,
                format_name=f"tensorrt-{precision}",
                output_path=output_path,
                export_time_s=export_time,
                file_size_mb=file_size_mb,
                success=True,
            )
        else:
            return ExportResult(
                model_name=model_name,
                format_name=f"tensorrt-{precision}",
                output_path=None,
                success=False,
                error="Export completed but output file not found",
            )

    except Exception as e:
        print(f"         FAILED: {e}")
        return ExportResult(
            model_name=model_name,
            format_name=f"tensorrt-{precision}",
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

    print(f"  [PyTorch] Benchmarking {model_name}...")

    try:
        clear_gpu_memory()
        vram_before = get_gpu_memory_mb()

        # Load model
        load_start = time.time()
        model = YOLO(str(model_path))
        model.to(device)
        result.load_time_s = time.time() - load_start

        result.file_size_mb = model_path.stat().st_size / (1024 * 1024)

        # Create test image
        test_image = create_test_image(input_size, input_size)

        # Warmup
        warmup_start = time.time()
        for _ in range(warmup_iterations):
            model(test_image, verbose=False)
        torch.cuda.synchronize()
        result.warmup_time_s = time.time() - warmup_start

        vram_after = get_gpu_memory_mb()
        result.vram_model_mb = vram_after - vram_before

        # Benchmark
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

        print(
            f"           {result.latency_mean_ms:.2f}ms ({result.throughput_fps:.0f} FPS), "
            f"VRAM: {result.vram_model_mb:.0f}MB"
        )

        del model
        clear_gpu_memory()

    except Exception as e:
        result.error = str(e)
        print(f"           FAILED: {e}")

    return result


def benchmark_yolo26_onnx(
    onnx_path: Path,
    input_size: int,
    warmup_iterations: int,
    benchmark_iterations: int,
) -> BenchmarkResult:
    """Benchmark YOLO26 model in ONNX format with CUDA Execution Provider."""
    import onnxruntime as ort

    model_name = onnx_path.stem
    result = BenchmarkResult(
        model_name=model_name,
        format_name="onnx-cuda",
        device="cuda:0",
        input_size=input_size,
        batch_size=1,
    )

    print(f"  [ONNX-CUDA] Benchmarking {model_name}...")

    try:
        clear_gpu_memory()
        vram_before = get_gpu_memory_mb()

        # Configure CUDA execution provider
        providers = [
            ("CUDAExecutionProvider", {"device_id": 0}),
            "CPUExecutionProvider",
        ]

        # Load model
        load_start = time.time()
        session = ort.InferenceSession(str(onnx_path), providers=providers)
        result.load_time_s = time.time() - load_start

        result.file_size_mb = onnx_path.stat().st_size / (1024 * 1024)

        # Get input info
        input_name = session.get_inputs()[0].name

        # Create test input (NCHW format, normalized)
        np.random.seed(42)
        test_input = np.random.rand(1, 3, input_size, input_size).astype(np.float32)

        # Warmup
        warmup_start = time.time()
        for _ in range(warmup_iterations):
            session.run(None, {input_name: test_input})
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        result.warmup_time_s = time.time() - warmup_start

        vram_after = get_gpu_memory_mb()
        result.vram_model_mb = vram_after - vram_before

        # Benchmark
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

        print(
            f"           {result.latency_mean_ms:.2f}ms ({result.throughput_fps:.0f} FPS), "
            f"VRAM: {result.vram_model_mb:.0f}MB"
        )

        del session
        clear_gpu_memory()

    except Exception as e:
        result.error = str(e)
        print(f"           FAILED: {e}")

    return result


def benchmark_yolo26_tensorrt(
    engine_path: Path,
    input_size: int,
    warmup_iterations: int,
    benchmark_iterations: int,
) -> BenchmarkResult:
    """Benchmark YOLO26 model in TensorRT engine format."""
    from ultralytics import YOLO

    model_name = engine_path.stem
    # Extract precision from filename (e.g., yolo26n_fp16.engine)
    precision = "fp16" if "fp16" in model_name else "fp32"
    base_name = model_name.replace("_fp16", "").replace("_fp32", "")

    result = BenchmarkResult(
        model_name=base_name,
        format_name=f"tensorrt-{precision}",
        device="cuda:0",
        input_size=input_size,
        batch_size=1,
    )

    print(f"  [TensorRT-{precision.upper()}] Benchmarking {base_name}...")

    try:
        clear_gpu_memory()
        vram_before = get_gpu_memory_mb()

        # Load TensorRT engine via Ultralytics
        load_start = time.time()
        model = YOLO(str(engine_path))
        result.load_time_s = time.time() - load_start

        result.file_size_mb = engine_path.stat().st_size / (1024 * 1024)

        # Create test image
        test_image = create_test_image(input_size, input_size)

        # Warmup (important for TensorRT to optimize)
        warmup_start = time.time()
        for _ in range(warmup_iterations):
            model(test_image, verbose=False)
        torch.cuda.synchronize()
        result.warmup_time_s = time.time() - warmup_start

        vram_after = get_gpu_memory_mb()
        result.vram_model_mb = vram_after - vram_before

        # Benchmark
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

        print(
            f"           {result.latency_mean_ms:.2f}ms ({result.throughput_fps:.0f} FPS), "
            f"VRAM: {result.vram_model_mb:.0f}MB"
        )

        del model
        clear_gpu_memory()

    except Exception as e:
        result.error = str(e)
        print(f"           FAILED: {e}")

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
        model_name="YOLO26-R101",
        format_name="pytorch",
        device=device,
        input_size=input_size,
        batch_size=1,
    )

    print("  [PyTorch] Benchmarking YOLO26...")

    try:
        clear_gpu_memory()
        vram_before = get_gpu_memory_mb()

        # Load model
        load_start = time.time()
        processor = AutoImageProcessor.from_pretrained(str(model_path))
        model = AutoModelForObjectDetection.from_pretrained(str(model_path))
        model = model.to(device)
        model.eval()
        result.load_time_s = time.time() - load_start

        # Create test image
        test_image = create_test_image(input_size, input_size)

        # Warmup
        warmup_start = time.time()
        for _ in range(warmup_iterations):
            inputs = processor(images=test_image, return_tensors="pt")
            inputs = {k: v.to(device) for k, v in inputs.items()}
            with torch.inference_mode():
                model(**inputs)
        torch.cuda.synchronize()
        result.warmup_time_s = time.time() - warmup_start

        vram_after = get_gpu_memory_mb()
        result.vram_model_mb = vram_after - vram_before

        # Benchmark
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

        print(
            f"           {result.latency_mean_ms:.2f}ms ({result.throughput_fps:.0f} FPS), "
            f"VRAM: {result.vram_model_mb:.0f}MB"
        )

        del model, processor
        clear_gpu_memory()

    except Exception as e:
        result.error = str(e)
        print(f"           FAILED: {e}")

    return result


# =============================================================================
# Report Generation
# =============================================================================


def generate_benchmark_report(
    results: list[BenchmarkResult],
    export_results: list[ExportResult],
    gpu_info: dict[str, Any],
    tensorrt_version: str,
) -> str:
    """Generate markdown report for GPU benchmarks."""
    lines = [
        "# YOLO26 vs YOLO26 GPU Benchmark Results",
        "",
        "> **Note:** This file is auto-generated by `scripts/benchmark_yolo26_container.py`.",
        "> To refresh results, run the benchmark inside the yolo26-benchmark container.",
        "",
        "## Environment",
        "",
        f"- **Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- **GPU:** {gpu_info.get('name', 'Unknown')}",
        f"- **VRAM:** {gpu_info.get('memory_total_mb', 0)} MB",
        f"- **Driver:** {gpu_info.get('driver_version', 'Unknown')}",
        f"- **CUDA:** {torch.version.cuda if torch.cuda.is_available() else 'N/A'}",
        f"- **TensorRT:** {tensorrt_version}",
        f"- **PyTorch:** {torch.__version__}",
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
            status = "SUCCESS" if exp.success else "FAILED"
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
        # Summary table sorted by latency
        lines.extend(
            [
                "## Benchmark Summary",
                "",
                "| Model | Format | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) | FPS | VRAM (MB) |",
                "|-------|--------|-----------|----------|----------|----------|-----|-----------|",
            ]
        )

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

        # Group by base model name
        models: dict[str, list[BenchmarkResult]] = {}
        for r in successful_results:
            base_name = r.model_name.replace("_fp16", "").replace("_fp32", "")
            if base_name not in models:
                models[base_name] = []
            models[base_name].append(r)

        for model_name in sorted(models.keys()):
            model_results = models[model_name]
            lines.extend(
                [
                    f"### {model_name}",
                    "",
                    "| Format | Mean | Std | Min | Max | P50 | P95 | P99 | FPS | VRAM | Load | Warmup |",
                    "|--------|------|-----|-----|-----|-----|-----|-----|-----|------|------|--------|",
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

        # TensorRT vs PyTorch speedup
        tensorrt_results = [r for r in successful_results if r.format_name.startswith("tensorrt")]
        pytorch_results = [
            r
            for r in successful_results
            if r.format_name == "pytorch" and "YOLO26" not in r.model_name
        ]

        if tensorrt_results and pytorch_results:
            lines.extend(
                [
                    "## TensorRT vs PyTorch Speedup",
                    "",
                    "| Model | PyTorch (ms) | TensorRT FP16 (ms) | Speedup | VRAM Savings |",
                    "|-------|--------------|-------------------|---------|--------------|",
                ]
            )
            for trt in tensorrt_results:
                if "fp16" not in trt.format_name:
                    continue
                base_name = trt.model_name.replace("_fp16", "").replace("_fp32", "")
                pt = next((r for r in pytorch_results if r.model_name == base_name), None)
                if pt:
                    speedup = pt.latency_mean_ms / trt.latency_mean_ms
                    vram_savings = pt.vram_model_mb - trt.vram_model_mb
                    lines.append(
                        f"| {base_name} | {pt.latency_mean_ms:.2f} | {trt.latency_mean_ms:.2f} | "
                        f"**{speedup:.2f}x** | {vram_savings:.0f} MB |"
                    )
            lines.append("")

        # Speedup vs YOLO26
        yolo26_result = next((r for r in successful_results if "YOLO26" in r.model_name), None)
        if yolo26_result:
            lines.extend(
                [
                    "## Speedup vs YOLO26 Baseline",
                    "",
                    f"**Baseline:** {yolo26_result.model_name} @ {yolo26_result.latency_mean_ms:.2f}ms ({yolo26_result.throughput_fps:.0f} FPS)",
                    "",
                    "| Model | Format | Speedup | Latency Reduction |",
                    "|-------|--------|---------|-------------------|",
                ]
            )
            for r in sorted(successful_results, key=lambda x: x.latency_mean_ms):
                if r != yolo26_result:
                    speedup = yolo26_result.latency_mean_ms / r.latency_mean_ms
                    reduction = (1 - r.latency_mean_ms / yolo26_result.latency_mean_ms) * 100
                    lines.append(
                        f"| {r.model_name} | {r.format_name} | **{speedup:.1f}x** | {reduction:.1f}% |"
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
        fastest = min(successful_results, key=lambda x: x.latency_mean_ms)
        lowest_vram = min(
            successful_results,
            key=lambda x: x.vram_model_mb if x.vram_model_mb > 0 else float("inf"),
        )
        best_fps = max(successful_results, key=lambda x: x.throughput_fps)

        lines.extend(
            [
                "### Best Performance",
                "",
                f"- **Fastest Inference:** {fastest.model_name} ({fastest.format_name}) @ {fastest.latency_mean_ms:.2f}ms ({fastest.throughput_fps:.0f} FPS)",
                f"- **Best Throughput:** {best_fps.model_name} ({best_fps.format_name}) @ {best_fps.throughput_fps:.0f} FPS",
                f"- **Lowest VRAM:** {lowest_vram.model_name} ({lowest_vram.format_name}) @ {lowest_vram.vram_model_mb:.0f} MB",
                "",
                "### Production Deployment",
                "",
            ]
        )

        # Find best TensorRT model
        trt_fp16 = [r for r in successful_results if r.format_name == "tensorrt-fp16"]
        if trt_fp16:
            best_trt = min(trt_fp16, key=lambda x: x.latency_mean_ms)
            lines.extend(
                [
                    f"**Recommended:** {best_trt.model_name} TensorRT FP16 engine",
                    "",
                    "TensorRT FP16 provides the best inference speed on NVIDIA GPUs with minimal accuracy loss.",
                    "",
                    "```yaml",
                    "# docker-compose.prod.yml configuration",
                    "ai-detector:",
                    "  environment:",
                    f"    DETECTOR_MODEL: /models/yolo26/exports/{best_trt.model_name}_fp16.engine",
                    "    DETECTOR_DEVICE: cuda:0",
                    "```",
                    "",
                ]
            )

            # Add accuracy note
            lines.extend(
                [
                    "### Accuracy Notes",
                    "",
                    "- TensorRT FP16 typically has <0.1% mAP loss vs FP32",
                    "- For maximum accuracy, use PyTorch or TensorRT FP32",
                    "- Run accuracy validation with `scripts/benchmark_yolo26_accuracy.py`",
                    "",
                ]
            )
        else:
            lines.extend(
                [
                    "**Note:** TensorRT FP16 engines not available. Export with:",
                    "",
                    "```bash",
                    "podman run --rm --device nvidia.com/gpu=all \\",
                    "    -v /export/ai_models/model-zoo:/models:z \\",
                    "    yolo26-benchmark python3 /scripts/benchmark_yolo26_container.py --export",
                    "```",
                    "",
                ]
            )

    return "\n".join(lines)


# =============================================================================
# Main Entry Point
# =============================================================================


def main() -> None:
    """Run GPU benchmarks for YOLO26 with TensorRT support."""
    parser = argparse.ArgumentParser(
        description="GPU benchmark for YOLO26 with native TensorRT support",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--export",
        action="store_true",
        help="Export models to ONNX and TensorRT before benchmarking",
    )
    parser.add_argument(
        "--export-only",
        action="store_true",
        help="Export models only, skip benchmarking",
    )
    parser.add_argument(
        "--skip-export",
        action="store_true",
        help="Skip export and benchmark existing files",
    )
    parser.add_argument(
        "--models",
        type=str,
        default="yolo26n,yolo26s,yolo26m,yolo26",
        help="Comma-separated list of models (default: yolo26n,yolo26s,yolo26m,yolo26)",
    )
    parser.add_argument(
        "--yolo-path",
        type=Path,
        default=DEFAULT_YOLO26_PATH,
        help=f"Path to YOLO26 models (default: {DEFAULT_YOLO26_PATH})",
    )
    parser.add_argument(
        "--yolo26-path",
        type=Path,
        default=DEFAULT_YOLO26_PATH,
        help=f"Path to YOLO26 model (default: {DEFAULT_YOLO26_PATH})",
    )
    parser.add_argument(
        "--export-path",
        type=Path,
        default=DEFAULT_EXPORT_PATH,
        help=f"Path for exports (default: {DEFAULT_EXPORT_PATH})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help=f"Output path for report (default: {DEFAULT_OUTPUT_PATH})",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=WARMUP_ITERATIONS,
        help=f"Warmup iterations (default: {WARMUP_ITERATIONS})",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=BENCHMARK_ITERATIONS,
        help=f"Benchmark iterations (default: {BENCHMARK_ITERATIONS})",
    )

    args = parser.parse_args()

    # Check CUDA availability
    if not torch.cuda.is_available():
        print("ERROR: CUDA is not available. This script requires a GPU.")
        print("Make sure to run with: podman run --device nvidia.com/gpu=all ...")
        sys.exit(1)

    # Parse model list
    model_names = [m.strip().lower() for m in args.models.split(",")]

    # Ensure directories exist
    args.export_path.mkdir(parents=True, exist_ok=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    # Get system info
    gpu_info = get_gpu_info()
    tensorrt_version = get_tensorrt_version()

    print("=" * 70)
    print("YOLO26 GPU Benchmark with TensorRT")
    print("=" * 70)
    print(f"GPU: {gpu_info.get('name', 'Unknown')}")
    print(f"VRAM: {gpu_info.get('memory_total_mb', 0)} MB")
    print(f"PyTorch: {torch.__version__}")
    print(f"CUDA: {torch.version.cuda}")
    print(f"TensorRT: {tensorrt_version}")
    print(f"Models: {model_names}")
    print(f"Export path: {args.export_path}")
    print(f"Warmup: {args.warmup} iterations")
    print(f"Benchmark: {args.iterations} iterations")
    print()

    export_results: list[ExportResult] = []
    benchmark_results: list[BenchmarkResult] = []

    # ==========================================================================
    # Export Phase
    # ==========================================================================

    if args.export or args.export_only:
        print("=" * 70)
        print("EXPORT PHASE")
        print("=" * 70)

        for model_name in model_names:
            if not model_name.startswith("yolo26"):
                continue

            model_path = args.yolo_path / f"{model_name}.pt"
            if not model_path.exists():
                print(f"\nWARNING: {model_path} not found, skipping export")
                continue

            print(f"\n{model_name.upper()}")
            print("-" * 40)

            # Export to ONNX
            result = export_yolo26_onnx(model_path, args.export_path)
            export_results.append(result)

            # Export to TensorRT FP16
            result = export_yolo26_tensorrt(model_path, args.export_path, half=True)
            export_results.append(result)

        if args.export_only:
            print("\n" + "=" * 70)
            print("Export complete. Skipping benchmarks (--export-only).")
            return

    # ==========================================================================
    # Benchmark Phase
    # ==========================================================================

    print("\n" + "=" * 70)
    print("BENCHMARK PHASE")
    print("=" * 70)

    for model_name in model_names:
        print(f"\n{model_name.upper()}")
        print("-" * 40)

        if model_name == "yolo26":
            if args.yolo26_path.exists():
                result = benchmark_yolo26(
                    args.yolo26_path,
                    INPUT_SIZE,
                    args.warmup,
                    args.iterations,
                )
                benchmark_results.append(result)
            else:
                print(f"  WARNING: {args.yolo26_path} not found, skipping")

        elif model_name.startswith("yolo26"):
            model_path = args.yolo_path / f"{model_name}.pt"

            if not model_path.exists():
                print(f"  WARNING: {model_path} not found, skipping")
                continue

            # Benchmark PyTorch
            result = benchmark_yolo26_pytorch(
                model_path,
                INPUT_SIZE,
                args.warmup,
                args.iterations,
            )
            benchmark_results.append(result)

            # Benchmark ONNX
            onnx_path = args.export_path / f"{model_name}.onnx"
            if onnx_path.exists():
                result = benchmark_yolo26_onnx(
                    onnx_path,
                    INPUT_SIZE,
                    args.warmup,
                    args.iterations,
                )
                benchmark_results.append(result)
            else:
                print(f"  [ONNX] Skipped - {onnx_path} not found")

            # Benchmark TensorRT FP16
            trt_path = args.export_path / f"{model_name}_fp16.engine"
            if trt_path.exists():
                result = benchmark_yolo26_tensorrt(
                    trt_path,
                    INPUT_SIZE,
                    args.warmup,
                    args.iterations,
                )
                benchmark_results.append(result)
            else:
                print(f"  [TensorRT] Skipped - {trt_path} not found")

    # ==========================================================================
    # Generate Report
    # ==========================================================================

    print("\n" + "=" * 70)
    print("GENERATING REPORT")
    print("=" * 70)

    report = generate_benchmark_report(
        benchmark_results,
        export_results,
        gpu_info,
        tensorrt_version,
    )

    args.output.write_text(report)
    print(f"\nReport saved to: {args.output}")

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

        fastest = min(successful, key=lambda x: x.latency_mean_ms)
        print(
            f"\nFastest: {fastest.model_name} ({fastest.format_name}) @ "
            f"{fastest.latency_mean_ms:.2f}ms ({fastest.throughput_fps:.0f} FPS)"
        )

    print("\nDone!")


if __name__ == "__main__":
    main()
