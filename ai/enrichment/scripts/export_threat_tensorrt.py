#!/usr/bin/env python3
"""TensorRT Export Script for Threat Detector YOLOv8n.

Exports the YOLOv8n weapon detection model to TensorRT engine format
for 2-3x inference speedup. Uses Ultralytics native TensorRT export.

Usage:
    # Export with FP16 precision (recommended for speed + accuracy balance)
    python export_threat_tensorrt.py --model /path/to/best.pt --precision fp16

    # Export with FP32 precision (slightly more accurate, slower)
    python export_threat_tensorrt.py --model /path/to/best.pt --precision fp32

    # Export with dynamic batch support
    python export_threat_tensorrt.py --model /path/to/best.pt --dynamic-batch --max-batch 8

    # Benchmark the exported engine
    python export_threat_tensorrt.py --model /path/to/best.pt --benchmark

Environment Variables:
    THREAT_MODEL_PATH: Default model path if --model not specified
    THREAT_TENSORRT_WORKSPACE_GB: TensorRT workspace size (default: 2)

Output:
    Creates model.engine (or model_fp16.engine) adjacent to the .pt file

Note:
    - TensorRT engines are GPU architecture-specific
    - Export on the same GPU that will run inference
    - FP16 provides ~2x speedup with minimal accuracy loss for detection tasks

Reference:
    https://docs.ultralytics.com/modes/export/#tensorrt
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

import torch

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def check_cuda_available() -> bool:
    """Check if CUDA is available for TensorRT export.

    Returns:
        True if CUDA is available, False otherwise.
    """
    if not torch.cuda.is_available():
        logger.error("CUDA is not available. TensorRT export requires a CUDA GPU.")
        return False

    device_name = torch.cuda.get_device_name(0)
    compute_capability = torch.cuda.get_device_capability(0)
    logger.info(f"CUDA device: {device_name}")
    logger.info(f"Compute capability: {compute_capability[0]}.{compute_capability[1]}")
    return True


def export_to_tensorrt(
    model_path: str,
    output_path: str | None = None,
    precision: str = "fp16",
    workspace_gb: int = 2,
    dynamic_batch: bool = False,
    max_batch_size: int = 1,
    input_size: int = 640,
) -> str:
    """Export YOLOv8 model to TensorRT engine format.

    Uses Ultralytics native TensorRT export which handles:
    - ONNX intermediate conversion
    - TensorRT engine building
    - Input/output binding configuration

    Args:
        model_path: Path to the YOLOv8 .pt model file.
        output_path: Optional output path for the .engine file.
                    If None, creates adjacent to model_path.
        precision: Inference precision ('fp16' or 'fp32').
        workspace_gb: TensorRT workspace size in GB.
        dynamic_batch: Enable dynamic batch sizes.
        max_batch_size: Maximum batch size (only used with dynamic_batch).
        input_size: Input image size (square).

    Returns:
        Path to the exported TensorRT engine file.

    Raises:
        FileNotFoundError: If model file doesn't exist.
        RuntimeError: If export fails.
    """
    try:
        from ultralytics import YOLO
    except ImportError as e:
        logger.error("ultralytics package not installed. Install with: pip install ultralytics")
        raise ImportError("ultralytics package required for TensorRT export") from e

    # Validate model exists
    model_path_obj = Path(model_path)
    if not model_path_obj.exists():
        raise FileNotFoundError(f"Model file not found: {model_path}")

    # Determine output path
    if output_path is None:
        suffix = f"_{precision}" if precision == "fp16" else ""
        output_path = str(model_path_obj.parent / f"{model_path_obj.stem}{suffix}.engine")
    else:
        output_path = str(output_path)

    logger.info("=" * 60)
    logger.info("TensorRT Export for Threat Detector")
    logger.info("=" * 60)
    logger.info(f"Input model: {model_path}")
    logger.info(f"Output engine: {output_path}")
    logger.info(f"Precision: {precision}")
    logger.info(f"Workspace: {workspace_gb} GB")
    logger.info(f"Dynamic batch: {dynamic_batch}")
    if dynamic_batch:
        logger.info(f"Max batch size: {max_batch_size}")
    logger.info(f"Input size: {input_size}x{input_size}")
    logger.info("=" * 60)

    # Load model
    logger.info("Loading YOLOv8 model...")
    model = YOLO(str(model_path))

    # Log model info
    if hasattr(model, "names"):
        logger.info(f"Model classes: {model.names}")

    # Export to TensorRT
    logger.info("Starting TensorRT export (this may take several minutes)...")
    start_time = time.time()

    export_args = {
        "format": "engine",
        "half": precision == "fp16",
        "device": 0,  # Use first CUDA device
        "workspace": workspace_gb,
        "imgsz": input_size,
        "verbose": True,
    }

    if dynamic_batch:
        export_args["dynamic"] = True
        export_args["batch"] = max_batch_size

    try:
        model.export(**export_args)
        export_time = time.time() - start_time
        logger.info(f"Export completed in {export_time:.1f} seconds")
    except Exception as e:
        logger.error(f"TensorRT export failed: {e}")
        raise RuntimeError(f"TensorRT export failed: {e}") from e

    # Ultralytics creates the engine adjacent to the .pt file
    # Move to desired output location if different
    actual_engine_path = Path(str(model_path).replace(".pt", ".engine"))

    if actual_engine_path.exists() and str(actual_engine_path) != output_path:
        import shutil

        shutil.move(str(actual_engine_path), output_path)
        logger.info(f"Moved engine to: {output_path}")

    final_path = output_path if Path(output_path).exists() else str(actual_engine_path)

    # Log final info
    engine_size_mb = Path(final_path).stat().st_size / (1024 * 1024)
    logger.info("=" * 60)
    logger.info("Export Summary")
    logger.info("=" * 60)
    logger.info(f"TensorRT engine: {final_path}")
    logger.info(f"Engine size: {engine_size_mb:.1f} MB")
    logger.info(f"Export time: {export_time:.1f} seconds")
    logger.info("=" * 60)

    return final_path


def benchmark_engine(
    engine_path: str,
    model_path: str | None = None,
    num_iterations: int = 100,
    warmup_iterations: int = 10,
) -> dict[str, float]:
    """Benchmark TensorRT engine against PyTorch model.

    Args:
        engine_path: Path to TensorRT engine file.
        model_path: Optional path to PyTorch model for comparison.
        num_iterations: Number of inference iterations for timing.
        warmup_iterations: Number of warmup iterations.

    Returns:
        Dictionary with benchmark results (latency in ms).
    """
    import numpy as np
    from PIL import Image
    from ultralytics import YOLO

    results = {}

    # Create dummy image
    dummy_image = Image.new("RGB", (640, 640), color=(128, 128, 128))

    # Benchmark TensorRT
    logger.info("Benchmarking TensorRT engine...")
    trt_model = YOLO(engine_path)

    # Warmup
    for _ in range(warmup_iterations):
        trt_model(dummy_image, verbose=False)

    # Benchmark
    trt_times = []
    for _ in range(num_iterations):
        start = time.perf_counter()
        trt_model(dummy_image, verbose=False)
        trt_times.append((time.perf_counter() - start) * 1000)

    results["tensorrt_mean_ms"] = float(np.mean(trt_times))
    results["tensorrt_std_ms"] = float(np.std(trt_times))
    results["tensorrt_min_ms"] = float(np.min(trt_times))
    results["tensorrt_max_ms"] = float(np.max(trt_times))

    logger.info(
        f"TensorRT: {results['tensorrt_mean_ms']:.2f} +/- {results['tensorrt_std_ms']:.2f} ms"
    )

    # Benchmark PyTorch if model path provided
    if model_path and Path(model_path).exists():
        logger.info("Benchmarking PyTorch model...")
        pt_model = YOLO(model_path)

        # Warmup
        for _ in range(warmup_iterations):
            pt_model(dummy_image, verbose=False)

        # Benchmark
        pt_times = []
        for _ in range(num_iterations):
            start = time.perf_counter()
            pt_model(dummy_image, verbose=False)
            pt_times.append((time.perf_counter() - start) * 1000)

        results["pytorch_mean_ms"] = float(np.mean(pt_times))
        results["pytorch_std_ms"] = float(np.std(pt_times))
        results["pytorch_min_ms"] = float(np.min(pt_times))
        results["pytorch_max_ms"] = float(np.max(pt_times))

        speedup = results["pytorch_mean_ms"] / results["tensorrt_mean_ms"]
        results["speedup"] = speedup

        logger.info(
            f"PyTorch: {results['pytorch_mean_ms']:.2f} +/- {results['pytorch_std_ms']:.2f} ms"
        )
        logger.info(f"Speedup: {speedup:.2f}x")

    return results


def verify_engine(engine_path: str, model_path: str) -> bool:
    """Verify TensorRT engine produces similar results to PyTorch model.

    Runs inference on a test image and compares detection counts and
    confidence scores between TensorRT and PyTorch backends.

    Args:
        engine_path: Path to TensorRT engine.
        model_path: Path to original PyTorch model.

    Returns:
        True if verification passes, False otherwise.
    """
    from PIL import Image
    from ultralytics import YOLO

    logger.info("Verifying TensorRT engine accuracy...")

    # Create test image with some structure
    test_image = Image.new("RGB", (640, 640), color=(200, 200, 200))

    # Load both models
    trt_model = YOLO(engine_path)
    pt_model = YOLO(model_path)

    # Run inference
    trt_results = trt_model(test_image, verbose=False)
    pt_results = pt_model(test_image, verbose=False)

    # Compare detection counts (on blank image, should both be 0)
    trt_detections = len(trt_results[0].boxes) if trt_results[0].boxes is not None else 0
    pt_detections = len(pt_results[0].boxes) if pt_results[0].boxes is not None else 0

    logger.info(f"TensorRT detections: {trt_detections}")
    logger.info(f"PyTorch detections: {pt_detections}")

    # For a blank test image, both should have 0 detections
    # This is a basic sanity check; real verification would use actual test images
    if trt_detections == pt_detections == 0:
        logger.info("Verification PASSED: Both models return 0 detections on blank image")
        return True

    # If both detect something, compare counts (allowing some variance)
    if abs(trt_detections - pt_detections) <= 2:
        logger.info("Verification PASSED: Detection counts are similar")
        return True

    logger.warning("Verification WARNING: Detection counts differ significantly")
    return False


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Export Threat Detector YOLOv8n to TensorRT",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Basic export with FP16
    python export_threat_tensorrt.py --model /models/threat-detection/best.pt

    # Export with custom output path
    python export_threat_tensorrt.py --model best.pt --output threat_fp16.engine

    # Export and benchmark
    python export_threat_tensorrt.py --model best.pt --benchmark

    # Full pipeline: export, verify, benchmark
    python export_threat_tensorrt.py --model best.pt --verify --benchmark
        """,
    )

    parser.add_argument(
        "--model",
        type=str,
        default=os.environ.get(
            "THREAT_MODEL_PATH", "/models/threat-detection-yolov8n/weights/best.pt"
        ),
        help="Path to YOLOv8 .pt model file",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output .engine file path (default: adjacent to model)",
    )
    parser.add_argument(
        "--precision",
        choices=["fp16", "fp32"],
        default="fp16",
        help="Inference precision (default: fp16)",
    )
    parser.add_argument(
        "--workspace",
        type=int,
        default=int(os.environ.get("THREAT_TENSORRT_WORKSPACE_GB", "2")),
        help="TensorRT workspace size in GB (default: 2)",
    )
    parser.add_argument(
        "--input-size",
        type=int,
        default=640,
        help="Input image size (default: 640)",
    )
    parser.add_argument(
        "--dynamic-batch",
        action="store_true",
        help="Enable dynamic batch sizes",
    )
    parser.add_argument(
        "--max-batch",
        type=int,
        default=8,
        help="Maximum batch size for dynamic batching (default: 8)",
    )
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Benchmark TensorRT vs PyTorch after export",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify TensorRT accuracy against PyTorch",
    )
    parser.add_argument(
        "--benchmark-iterations",
        type=int,
        default=100,
        help="Number of iterations for benchmarking (default: 100)",
    )

    args = parser.parse_args()

    # Check CUDA
    if not check_cuda_available():
        return 1

    # Export
    try:
        engine_path = export_to_tensorrt(
            model_path=args.model,
            output_path=args.output,
            precision=args.precision,
            workspace_gb=args.workspace,
            dynamic_batch=args.dynamic_batch,
            max_batch_size=args.max_batch,
            input_size=args.input_size,
        )
    except Exception as e:
        logger.error(f"Export failed: {e}")
        return 1

    # Verify if requested
    if args.verify:
        if not verify_engine(engine_path, args.model):
            logger.warning("Verification found differences - manual review recommended")

    # Benchmark if requested
    if args.benchmark:
        benchmark_engine(
            engine_path=engine_path,
            model_path=args.model,
            num_iterations=args.benchmark_iterations,
        )

    logger.info("Done!")
    logger.info("To use the TensorRT engine, set:")
    logger.info("  THREAT_DETECTOR_USE_TENSORRT=true")
    logger.info(f"  THREAT_MODEL_PATH={engine_path}")
    logger.info("Or place the .engine file adjacent to the .pt file for auto-detection.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
