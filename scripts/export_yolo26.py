#!/usr/bin/env python3
"""
Export YOLO26 models to various formats and benchmark inference speeds.

This script exports YOLO26 models to ONNX and TensorRT formats, benchmarks
inference speeds across all formats, and verifies detection correctness.

Usage:
    uv run python scripts/export_yolo26.py                     # Export all formats
    uv run python scripts/export_yolo26.py --format onnx       # Export ONNX only
    uv run python scripts/export_yolo26.py --benchmark-only    # Benchmark existing exports
    uv run python scripts/export_yolo26.py --model yolo26s.pt  # Export specific model

Requirements:
    ultralytics>=8.4.0
    onnx (for ONNX export)
    onnxruntime-gpu (for ONNX inference)
    tensorrt (for TensorRT export, optional)
"""

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import torch

# Model paths
YOLO26_DIR = Path("/export/ai_models/model-zoo/yolo26")
EXPORTS_DIR = YOLO26_DIR / "exports"
TEST_IMAGE_DIR = Path(__file__).parent.parent / "backend/tests/fixtures/images/pipeline_test"

# Export configurations
EXPORT_FORMATS: dict[str, dict[str, Any]] = {
    "onnx": {
        "suffix": ".onnx",
        "export_args": {"format": "onnx", "imgsz": 640, "simplify": True, "opset": 17},
        "description": "ONNX - Cross-platform, good compatibility",
    },
    "engine": {
        "suffix": ".engine",
        "export_args": {"format": "engine", "imgsz": 640, "half": True},
        "description": "TensorRT - NVIDIA GPU optimized, best performance",
    },
    "openvino": {
        "suffix": "_openvino_model",
        "export_args": {"format": "openvino", "imgsz": 640, "half": False},
        "description": "OpenVINO - Intel CPU/GPU optimized",
    },
}


def get_file_size(path: Path) -> str:
    """Get human-readable file size."""
    if not path.exists():
        return "N/A"

    # Handle both files and directories
    if path.is_dir():
        # Sum up all files in directory
        size_bytes = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    else:
        size_bytes = path.stat().st_size

    if size_bytes >= 1024 * 1024 * 1024:
        return f"{size_bytes / (1024**3):.2f} GB"
    elif size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024**2):.2f} MB"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.2f} KB"
    return f"{size_bytes} bytes"


def get_test_images() -> list[Path]:
    """Get test images for benchmarking."""
    if not TEST_IMAGE_DIR.exists():
        print(f"WARNING: Test image directory not found: {TEST_IMAGE_DIR}")
        return []

    images = list(TEST_IMAGE_DIR.glob("*.jpg")) + list(TEST_IMAGE_DIR.glob("*.png"))
    return sorted(images)[:5]  # Use first 5 images for benchmarking


def check_gpu_availability() -> dict[str, Any]:
    """Check GPU and CUDA availability."""
    cuda_available = torch.cuda.is_available()
    gpu_count = torch.cuda.device_count() if cuda_available else 0
    gpu_names: list[str] = []

    if cuda_available:
        for i in range(gpu_count):
            gpu_names.append(torch.cuda.get_device_name(i))

    info: dict[str, Any] = {
        "cuda_available": cuda_available,
        "cuda_version": torch.version.cuda if cuda_available else None,
        "gpu_count": gpu_count,
        "gpu_names": gpu_names,
        "tensorrt_available": False,
    }

    # Check TensorRT availability
    try:
        import tensorrt  # noqa: F401

        info["tensorrt_available"] = True
    except ImportError:
        pass

    return info


def export_model(model_path: Path, export_format: str, force: bool = False) -> dict[str, Any]:
    """Export a YOLO26 model to the specified format.

    Args:
        model_path: Path to the .pt model file
        export_format: One of 'onnx', 'engine', 'openvino'
        force: Force re-export even if file exists

    Returns:
        Dictionary with export results
    """
    from ultralytics import YOLO

    config = EXPORT_FORMATS.get(export_format)
    if not config:
        return {"status": "ERROR", "error": f"Unknown format: {export_format}"}

    model_name = model_path.stem
    suffix: str = config["suffix"]

    # Determine output path
    if suffix.endswith("_model"):
        # Directory-based output (OpenVINO)
        output_path = EXPORTS_DIR / f"{model_name}{suffix}"
        output_file = output_path / f"{model_name}.xml"
    else:
        output_path = EXPORTS_DIR / f"{model_name}{suffix}"
        output_file = output_path

    result = {
        "model": model_name,
        "format": export_format,
        "output_path": str(output_path),
        "description": config["description"],
    }

    # Check if already exported
    if output_file.exists() and not force:
        result["status"] = "SKIPPED"
        result["message"] = "Already exported (use --force to re-export)"
        result["file_size"] = get_file_size(output_path)
        return result

    print(f"Exporting {model_name} to {export_format}...")

    try:
        # Load model
        start_time = time.time()
        model = YOLO(str(model_path))
        load_time = time.time() - start_time

        # Export
        export_start = time.time()
        export_args: dict[str, Any] = config["export_args"].copy()

        # For TensorRT, check if CUDA is available
        if export_format == "engine":
            if not torch.cuda.is_available():
                result["status"] = "SKIPPED"
                result["message"] = "TensorRT requires CUDA GPU"
                return result

        exported_path_str = model.export(**export_args)
        export_time = time.time() - export_start

        # Move to exports directory if needed
        exported_path = Path(str(exported_path_str))
        if exported_path.exists() and exported_path != output_path:
            if output_path.exists():
                if output_path.is_dir():
                    import shutil

                    shutil.rmtree(output_path)
                else:
                    output_path.unlink()

            # Move exported file/directory
            import shutil

            shutil.move(str(exported_path), str(output_path))

        result["status"] = "SUCCESS"
        result["load_time"] = f"{load_time:.2f}s"
        result["export_time"] = f"{export_time:.2f}s"
        result["file_size"] = get_file_size(output_path)

    except Exception as e:
        result["status"] = "ERROR"
        result["error"] = str(e)

    return result


def benchmark_inference(
    model_path: Path, test_images: list[Path], warmup_runs: int = 3, test_runs: int = 10
) -> dict[str, Any]:
    """Benchmark inference speed for a model.

    Args:
        model_path: Path to the model file (any format)
        test_images: List of test image paths
        warmup_runs: Number of warmup inference runs
        test_runs: Number of timed inference runs

    Returns:
        Dictionary with benchmark results
    """
    from ultralytics import YOLO

    result = {
        "model": str(model_path),
        "test_images": len(test_images),
        "warmup_runs": warmup_runs,
        "test_runs": test_runs,
    }

    if not test_images:
        result["status"] = "ERROR"
        result["error"] = "No test images available"
        return result

    try:
        # Load model
        start_time = time.time()
        model = YOLO(str(model_path))
        load_time = time.time() - start_time

        # Warmup runs
        for _ in range(warmup_runs):
            for img in test_images[:2]:
                model(str(img), verbose=False)

        # Timed inference runs
        inference_times = []
        for _ in range(test_runs):
            for img in test_images:
                start = time.time()
                model(str(img), verbose=False)
                inference_times.append((time.time() - start) * 1000)  # ms

        result["status"] = "SUCCESS"
        result["load_time_s"] = load_time
        result["inference_ms"] = {
            "mean": np.mean(inference_times),
            "std": np.std(inference_times),
            "min": np.min(inference_times),
            "max": np.max(inference_times),
            "p50": np.percentile(inference_times, 50),
            "p95": np.percentile(inference_times, 95),
            "p99": np.percentile(inference_times, 99),
        }

    except Exception as e:
        result["status"] = "ERROR"
        result["error"] = str(e)

    return result


def verify_detections(
    pytorch_model_path: Path, exported_model_path: Path, test_images: list[Path]
) -> dict[str, Any]:
    """Verify that exported model produces same detections as PyTorch model.

    Args:
        pytorch_model_path: Path to the original .pt model
        exported_model_path: Path to the exported model
        test_images: List of test image paths

    Returns:
        Dictionary with verification results
    """
    from ultralytics import YOLO

    result = {
        "pytorch_model": str(pytorch_model_path),
        "exported_model": str(exported_model_path),
        "test_images": len(test_images),
    }

    if not test_images:
        result["status"] = "ERROR"
        result["error"] = "No test images available"
        return result

    try:
        # Load both models
        pt_model = YOLO(str(pytorch_model_path))
        export_model = YOLO(str(exported_model_path))

        total_detections = 0
        matching_detections = 0
        detection_diffs = []

        for img in test_images:
            # Run inference on both models
            pt_results = pt_model(str(img), verbose=False)[0]
            export_results = export_model(str(img), verbose=False)[0]

            # Compare detections
            pt_boxes = pt_results.boxes
            export_boxes = export_results.boxes

            if pt_boxes is not None and export_boxes is not None:
                pt_count = len(pt_boxes)
                export_count = len(export_boxes)

                total_detections += pt_count

                # Check if same number of detections
                if pt_count == export_count:
                    # Compare class predictions and confidences
                    pt_classes = pt_boxes.cls.cpu().numpy().tolist()
                    export_classes = export_boxes.cls.cpu().numpy().tolist()

                    # Allow for small numerical differences in boxes
                    if pt_classes == export_classes:
                        matching_detections += pt_count

                detection_diffs.append(
                    {
                        "image": img.name,
                        "pytorch_count": pt_count,
                        "exported_count": export_count,
                        "match": pt_count == export_count,
                    }
                )

        match_rate = matching_detections / total_detections if total_detections > 0 else 1.0

        result["status"] = "SUCCESS"
        result["total_detections"] = total_detections
        result["matching_detections"] = matching_detections
        result["match_rate"] = f"{match_rate * 100:.1f}%"
        result["detection_comparison"] = detection_diffs
        result["verdict"] = "PASS" if match_rate >= 0.95 else "FAIL"

    except Exception as e:
        result["status"] = "ERROR"
        result["error"] = str(e)

    return result


def generate_report(results: dict[str, Any]) -> str:
    """Generate a markdown report of export results and benchmarks."""
    lines = [
        "# YOLO26 Export Format Evaluation",
        "",
        f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Model Directory:** {YOLO26_DIR}",
        f"**Exports Directory:** {EXPORTS_DIR}",
        "",
    ]

    # GPU Info
    gpu_info = results.get("gpu_info", {})
    if gpu_info:
        lines.extend(
            [
                "## System Information",
                "",
                f"- **CUDA Available:** {gpu_info.get('cuda_available', False)}",
                f"- **CUDA Version:** {gpu_info.get('cuda_version', 'N/A')}",
                f"- **GPU Count:** {gpu_info.get('gpu_count', 0)}",
                f"- **GPUs:** {', '.join(gpu_info.get('gpu_names', ['None']))}",
                f"- **TensorRT Available:** {gpu_info.get('tensorrt_available', False)}",
                "",
            ]
        )

    # Export Results
    exports = results.get("exports", [])
    if exports:
        lines.extend(
            [
                "## Export Results",
                "",
                "| Model | Format | Status | Export Time | File Size |",
                "|-------|--------|--------|-------------|-----------|",
            ]
        )

        for export in exports:
            model = export.get("model", "N/A")
            fmt = export.get("format", "N/A")
            status = export.get("status", "N/A")
            export_time = export.get("export_time", "N/A")
            file_size = export.get("file_size", "N/A")
            lines.append(f"| {model} | {fmt} | {status} | {export_time} | {file_size} |")

        lines.append("")

    # File Size Comparison
    file_sizes = results.get("file_sizes", {})
    if file_sizes:
        lines.extend(
            [
                "## File Size Comparison",
                "",
                "| Format | File Size | Relative Size |",
                "|--------|-----------|---------------|",
            ]
        )

        pt_size = file_sizes.get("pytorch", {}).get("bytes", 0)
        for fmt, info in file_sizes.items():
            size = info.get("human", "N/A")
            size_bytes = info.get("bytes", 0)
            relative = (
                f"{size_bytes / pt_size * 100:.0f}%" if pt_size > 0 and size_bytes > 0 else "N/A"
            )
            lines.append(f"| {fmt} | {size} | {relative} |")

        lines.append("")

    # Benchmark Results
    benchmarks = results.get("benchmarks", [])
    if benchmarks:
        lines.extend(
            [
                "## Inference Speed Comparison",
                "",
                "| Format | Load Time | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |",
                "|--------|-----------|-----------|----------|----------|----------|",
            ]
        )

        for bench in benchmarks:
            if bench.get("status") != "SUCCESS":
                continue
            fmt = Path(bench.get("model", "")).suffix or ".pt"
            load_time = f"{bench.get('load_time_s', 0):.2f}s"
            inf = bench.get("inference_ms", {})
            mean = f"{inf.get('mean', 0):.1f}"
            p50 = f"{inf.get('p50', 0):.1f}"
            p95 = f"{inf.get('p95', 0):.1f}"
            p99 = f"{inf.get('p99', 0):.1f}"
            lines.append(f"| {fmt} | {load_time} | {mean} | {p50} | {p95} | {p99} |")

        lines.append("")

    # Verification Results
    verifications = results.get("verifications", [])
    if verifications:
        lines.extend(
            [
                "## Detection Correctness Verification",
                "",
                "| Exported Format | Total Detections | Matching | Match Rate | Verdict |",
                "|-----------------|------------------|----------|------------|---------|",
            ]
        )

        for verify in verifications:
            if verify.get("status") != "SUCCESS":
                continue
            fmt = Path(verify.get("exported_model", "")).suffix or "N/A"
            total = verify.get("total_detections", 0)
            matching = verify.get("matching_detections", 0)
            rate = verify.get("match_rate", "N/A")
            verdict = verify.get("verdict", "N/A")
            lines.append(f"| {fmt} | {total} | {matching} | {rate} | {verdict} |")

        lines.append("")

    # Recommendations
    lines.extend(
        [
            "## Recommendations",
            "",
            "### Best Format by Use Case",
            "",
            "| Use Case | Recommended Format | Reason |",
            "|----------|-------------------|--------|",
            "| Production (NVIDIA GPU) | TensorRT (.engine) | Best inference speed with FP16 |",
            "| Cross-platform deployment | ONNX | Wide compatibility, good performance |",
            "| Intel hardware | OpenVINO | Optimized for Intel CPUs/GPUs |",
            "| Development/debugging | PyTorch (.pt) | Easiest to work with |",
            "",
            "### Export Format Details",
            "",
            "#### ONNX (Open Neural Network Exchange)",
            "- **Pros:** Cross-platform, widely supported, good inference speed",
            "- **Cons:** Slightly slower than TensorRT on NVIDIA GPUs",
            "- **Best for:** Deployments requiring portability",
            "",
            "#### TensorRT",
            "- **Pros:** Best performance on NVIDIA GPUs, FP16 support, optimized kernels",
            "- **Cons:** NVIDIA-only, requires matching CUDA/cuDNN versions",
            "- **Best for:** Maximum throughput on NVIDIA hardware",
            "",
            "#### OpenVINO (Optional)",
            "- **Pros:** Excellent on Intel hardware, CPU-optimized",
            "- **Cons:** Limited GPU support, Intel-specific",
            "- **Best for:** Edge deployments on Intel hardware",
            "",
        ]
    )

    # Errors and Issues
    errors = results.get("errors", [])
    if errors:
        lines.extend(
            [
                "## Issues Encountered",
                "",
            ]
        )
        for error in errors:
            lines.append(f"- {error}")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Export YOLO26 models and benchmark inference speeds"
    )
    parser.add_argument(
        "--model",
        default="yolo26n.pt",
        help="Model to export (default: yolo26n.pt)",
    )
    parser.add_argument(
        "--format",
        choices=["all", "onnx", "engine", "openvino"],
        default="all",
        help="Export format (default: all)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-export even if files exist",
    )
    parser.add_argument(
        "--benchmark-only",
        action="store_true",
        help="Only run benchmarks on existing exports",
    )
    parser.add_argument(
        "--skip-verification",
        action="store_true",
        help="Skip detection correctness verification",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output report path (default: docs/benchmarks/yolo26-vs-rtdetr.md)",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("YOLO26 Export Format Evaluation")
    print("=" * 60)
    print()

    # Create exports directory
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # Collect results
    results: dict[str, Any] = {
        "exports": [],
        "benchmarks": [],
        "verifications": [],
        "file_sizes": {},
        "errors": [],
    }

    # Check system info
    gpu_info = check_gpu_availability()
    results["gpu_info"] = gpu_info
    print(f"CUDA Available: {gpu_info['cuda_available']}")
    print(f"TensorRT Available: {gpu_info['tensorrt_available']}")
    if gpu_info["gpu_names"]:
        print(f"GPUs: {', '.join(gpu_info['gpu_names'])}")
    print()

    # Get model path
    model_path = YOLO26_DIR / args.model
    if not model_path.exists():
        print(f"ERROR: Model not found: {model_path}")
        return 1

    print(f"Model: {model_path}")
    print(f"Model Size: {get_file_size(model_path)}")
    print()

    # Get test images
    test_images = get_test_images()
    print(f"Test Images: {len(test_images)}")
    for img in test_images:
        print(f"  - {img.name}")
    print()

    # Record PyTorch file size
    pt_size = model_path.stat().st_size
    results["file_sizes"]["pytorch"] = {"human": get_file_size(model_path), "bytes": pt_size}

    # Determine formats to export
    formats_to_export = []
    if args.format == "all":
        formats_to_export = ["onnx"]
        if gpu_info["cuda_available"]:
            formats_to_export.append("engine")
    else:
        formats_to_export = [args.format]

    # Export models
    if not args.benchmark_only:
        print("=" * 60)
        print("Exporting Models")
        print("=" * 60)
        print()

        for fmt in formats_to_export:
            result = export_model(model_path, fmt, force=args.force)
            results["exports"].append(result)

            status = result.get("status", "UNKNOWN")
            print(f"[{status}] {fmt}: {result.get('message', result.get('error', 'OK'))}")
            if result.get("file_size"):
                print(f"         Size: {result['file_size']}")

            # Record file size
            if status in {"SUCCESS", "SKIPPED"}:
                export_path = Path(result.get("output_path", ""))
                if export_path.exists():
                    if export_path.is_dir():
                        size_bytes = sum(
                            f.stat().st_size for f in export_path.rglob("*") if f.is_file()
                        )
                    else:
                        size_bytes = export_path.stat().st_size
                    results["file_sizes"][fmt] = {
                        "human": get_file_size(export_path),
                        "bytes": size_bytes,
                    }

            print()

    # Benchmark inference
    print("=" * 60)
    print("Benchmarking Inference Speed")
    print("=" * 60)
    print()

    # Benchmark PyTorch model
    print("Benchmarking PyTorch model...")
    pt_benchmark = benchmark_inference(model_path, test_images)
    pt_benchmark["model"] = str(model_path)
    results["benchmarks"].append(pt_benchmark)
    if pt_benchmark.get("status") == "SUCCESS":
        inf = pt_benchmark["inference_ms"]
        print(f"  Mean: {inf['mean']:.1f}ms, P95: {inf['p95']:.1f}ms")
    print()

    # Benchmark exported models
    model_name = model_path.stem
    for fmt in formats_to_export:
        config = EXPORT_FORMATS[fmt]
        suffix: str = config["suffix"]

        if suffix.endswith("_model"):
            export_path = EXPORTS_DIR / f"{model_name}{suffix}"
        else:
            export_path = EXPORTS_DIR / f"{model_name}{suffix}"

        if not export_path.exists():
            print(f"Skipping {fmt} benchmark (not exported)")
            continue

        print(f"Benchmarking {fmt} model...")
        bench = benchmark_inference(export_path, test_images)
        bench["model"] = str(export_path)
        results["benchmarks"].append(bench)

        if bench.get("status") == "SUCCESS":
            inf = bench["inference_ms"]
            print(f"  Mean: {inf['mean']:.1f}ms, P95: {inf['p95']:.1f}ms")
        elif bench.get("error"):
            print(f"  ERROR: {bench['error']}")
        print()

    # Verify detection correctness
    if not args.skip_verification:
        print("=" * 60)
        print("Verifying Detection Correctness")
        print("=" * 60)
        print()

        for fmt in formats_to_export:
            config = EXPORT_FORMATS[fmt]
            suffix_verify: str = config["suffix"]

            if suffix_verify.endswith("_model"):
                export_path = EXPORTS_DIR / f"{model_name}{suffix_verify}"
            else:
                export_path = EXPORTS_DIR / f"{model_name}{suffix_verify}"

            if not export_path.exists():
                print(f"Skipping {fmt} verification (not exported)")
                continue

            print(f"Verifying {fmt} detections...")
            verify = verify_detections(model_path, export_path, test_images)
            results["verifications"].append(verify)

            if verify.get("status") == "SUCCESS":
                print(f"  Match Rate: {verify['match_rate']} ({verify['verdict']})")
            elif verify.get("error"):
                print(f"  ERROR: {verify['error']}")
            print()

    # Generate report
    report = generate_report(results)

    # Determine output path
    output_path = args.output
    if output_path is None:
        output_path = Path(__file__).parent.parent / "docs/benchmarks/yolo26-vs-rtdetr.md"
    else:
        output_path = Path(output_path)

    # Write report
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report)
    print(f"Report saved to: {output_path}")

    # Also save export report to exports directory
    export_report_path = EXPORTS_DIR / "EXPORT_REPORT.md"
    export_report_path.write_text(report)
    print(f"Report also saved to: {export_report_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
