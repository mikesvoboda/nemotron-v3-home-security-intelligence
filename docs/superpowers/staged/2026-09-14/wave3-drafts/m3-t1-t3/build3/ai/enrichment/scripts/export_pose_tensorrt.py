#!/usr/bin/env python3
"""Export YOLOv8n-pose to TensorRT engine format.

This script exports the YOLOv8n-pose model to a TensorRT engine for
accelerated inference (2-3x speedup over PyTorch).

Usage:
    # Export with default settings (FP16 precision)
    python export_pose_tensorrt.py

    # Export with custom model path
    python export_pose_tensorrt.py --model /path/to/yolov8n-pose.pt

    # Export with FP32 precision (larger, slower, but more accurate)
    python export_pose_tensorrt.py --precision fp32

    # Export to specific output path
    python export_pose_tensorrt.py --output /path/to/output.engine

    # Specify GPU device
    python export_pose_tensorrt.py --device 0

Requirements:
    - NVIDIA GPU with CUDA support
    - TensorRT installed (pip install tensorrt)
    - ultralytics package (pip install ultralytics)

Note:
    TensorRT engines are GPU-architecture specific. An engine built on
    one GPU (e.g., RTX 3090) may not work on another GPU (e.g., RTX 4090).
    You must rebuild the engine for each target GPU architecture.

Environment Variables:
    POSE_MODEL_PATH: Default path to the YOLOv8n-pose model
    POSE_TENSORRT_ENGINE_PATH: Default output path for the engine

Reference:
    https://docs.ultralytics.com/modes/export/
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Valid precision modes
VALID_PRECISIONS = frozenset({"fp16", "fp32"})


def check_requirements() -> bool:
    """Check if all required packages are installed.

    Returns:
        True if all requirements are met, False otherwise.
    """
    errors = []

    # Check CUDA
    try:
        import torch

        if not torch.cuda.is_available():
            errors.append("CUDA is not available. TensorRT requires a CUDA-capable GPU.")
        else:
            logger.info(f"CUDA available: {torch.cuda.get_device_name(0)}")
    except ImportError:
        errors.append("PyTorch is not installed. Install with: pip install torch")

    # Check TensorRT
    try:
        import tensorrt as trt

        logger.info(f"TensorRT version: {trt.__version__}")
    except ImportError:
        errors.append("TensorRT is not installed. Install with: pip install tensorrt")

    # Check ultralytics
    try:
        import ultralytics
        from ultralytics import YOLO

        logger.info(f"Ultralytics version: {ultralytics.__version__}")
    except ImportError:
        errors.append("Ultralytics is not installed. Install with: pip install ultralytics")

    if errors:
        for error in errors:
            logger.error(error)
        return False

    return True


def get_default_model_path() -> str:
    """Get the default model path from environment or fallback.

    Returns:
        Path to the YOLOv8n-pose model.
    """
    return os.environ.get("POSE_MODEL_PATH", "/models/yolov8n-pose/yolov8n-pose.pt")


def get_default_output_path(model_path: str) -> str:
    """Get the default output path based on model path.

    Args:
        model_path: Path to the input model.

    Returns:
        Path for the output engine file.
    """
    custom_path = os.environ.get("POSE_TENSORRT_ENGINE_PATH")
    if custom_path:
        return custom_path

    model_path_obj = Path(model_path)
    return str(model_path_obj.with_suffix(".engine"))


def export_to_tensorrt(
    model_path: str,
    output_path: str | None = None,
    precision: str = "fp16",
    device: int = 0,
    workspace_gb: int = 4,
    verbose: bool = False,
) -> str:
    """Export YOLOv8n-pose model to TensorRT engine.

    Args:
        model_path: Path to the YOLOv8n-pose PyTorch model (.pt file).
        output_path: Path for the output engine file. If None, auto-generated.
        precision: TensorRT precision ('fp16' or 'fp32').
        device: CUDA device index for export.
        workspace_gb: TensorRT workspace size in GB.
        verbose: Enable verbose logging during export.

    Returns:
        Path to the exported engine file.

    Raises:
        FileNotFoundError: If model file doesn't exist.
        ValueError: If precision is invalid.
        RuntimeError: If export fails.
    """
    from ultralytics import YOLO

    # Validate inputs
    if precision not in VALID_PRECISIONS:
        raise ValueError(f"precision must be one of {VALID_PRECISIONS}, got '{precision}'")

    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model file not found: {model_path}")

    # Determine output path
    if output_path is None:
        output_path = get_default_output_path(model_path)

    logger.info("=" * 60)
    logger.info("YOLOv8n-pose TensorRT Export")
    logger.info("=" * 60)
    logger.info(f"Input model:  {model_path}")
    logger.info(f"Output engine: {output_path}")
    logger.info(f"Precision:    {precision.upper()}")
    logger.info(f"Device:       cuda:{device}")
    logger.info(f"Workspace:    {workspace_gb} GB")
    logger.info("=" * 60)

    # Check if output already exists
    if os.path.exists(output_path):
        logger.warning(f"Output file already exists: {output_path}")
        response = input("Overwrite? [y/N]: ").strip().lower()
        if response != "y":
            logger.info("Export cancelled.")
            return output_path

    # Load model
    logger.info("Loading YOLOv8n-pose model...")
    start_time = time.time()
    model = YOLO(model_path)
    load_time = time.time() - start_time
    logger.info(f"Model loaded in {load_time:.2f} seconds")

    # Export to TensorRT
    logger.info("Exporting to TensorRT (this may take several minutes)...")
    export_start = time.time()

    try:
        exported = model.export(
            format="engine",
            half=(precision == "fp16"),
            device=device,
            workspace=workspace_gb,
            verbose=verbose,
        )

        export_time = time.time() - export_start
        logger.info(f"Export completed in {export_time:.1f} seconds")

        # Verify output
        if exported and os.path.exists(str(exported)):
            engine_path = str(exported)
        elif os.path.exists(output_path):
            engine_path = output_path
        else:
            # Ultralytics may put the engine next to the .pt file
            auto_path = Path(model_path).with_suffix(".engine")
            if os.path.exists(auto_path):
                engine_path = str(auto_path)
            else:
                raise RuntimeError("Export completed but engine file not found")

        # Get file sizes
        pt_size = Path(model_path).stat().st_size / (1024 * 1024)
        engine_size = Path(engine_path).stat().st_size / (1024 * 1024)

        logger.info("=" * 60)
        logger.info("Export Successful!")
        logger.info("=" * 60)
        logger.info(f"Engine file:   {engine_path}")
        logger.info(f"PyTorch size:  {pt_size:.1f} MB")
        logger.info(f"Engine size:   {engine_size:.1f} MB")
        logger.info(f"Total time:    {load_time + export_time:.1f} seconds")
        logger.info("=" * 60)
        logger.info("")
        logger.info("To use TensorRT acceleration, set:")
        logger.info("  export POSE_USE_TENSORRT=true")
        logger.info("")

        return engine_path

    except Exception as e:
        logger.error(f"Export failed: {e}")
        raise RuntimeError(f"TensorRT export failed: {e}") from e


def benchmark_engines(
    pt_path: str,
    engine_path: str,
    device: int = 0,
    warmup_runs: int = 5,
    benchmark_runs: int = 20,
) -> dict[str, float]:
    """Benchmark PyTorch vs TensorRT inference speed.

    Args:
        pt_path: Path to PyTorch model.
        engine_path: Path to TensorRT engine.
        device: CUDA device index.
        warmup_runs: Number of warmup iterations.
        benchmark_runs: Number of benchmark iterations.

    Returns:
        Dictionary with timing results.
    """
    import numpy as np
    from PIL import Image
    from ultralytics import YOLO

    logger.info("=" * 60)
    logger.info("Benchmarking PyTorch vs TensorRT")
    logger.info("=" * 60)

    # Create dummy image
    dummy_image = Image.new("RGB", (640, 480), color=(128, 128, 128))
    image_array = np.array(dummy_image)

    results = {}

    # Benchmark PyTorch
    logger.info("Loading PyTorch model...")
    pt_model = YOLO(pt_path)
    pt_model.to(f"cuda:{device}")

    logger.info(f"Warming up PyTorch ({warmup_runs} runs)...")
    for _ in range(warmup_runs):
        pt_model(image_array, verbose=False)

    logger.info(f"Benchmarking PyTorch ({benchmark_runs} runs)...")
    pt_times = []
    for _ in range(benchmark_runs):
        start = time.perf_counter()
        pt_model(image_array, verbose=False)
        pt_times.append((time.perf_counter() - start) * 1000)

    results["pytorch_avg_ms"] = sum(pt_times) / len(pt_times)
    results["pytorch_min_ms"] = min(pt_times)
    results["pytorch_max_ms"] = max(pt_times)

    del pt_model
    import torch

    torch.cuda.empty_cache()

    # Benchmark TensorRT
    logger.info("Loading TensorRT engine...")
    trt_model = YOLO(engine_path)

    logger.info(f"Warming up TensorRT ({warmup_runs} runs)...")
    for _ in range(warmup_runs):
        trt_model(image_array, verbose=False)

    logger.info(f"Benchmarking TensorRT ({benchmark_runs} runs)...")
    trt_times = []
    for _ in range(benchmark_runs):
        start = time.perf_counter()
        trt_model(image_array, verbose=False)
        trt_times.append((time.perf_counter() - start) * 1000)

    results["tensorrt_avg_ms"] = sum(trt_times) / len(trt_times)
    results["tensorrt_min_ms"] = min(trt_times)
    results["tensorrt_max_ms"] = max(trt_times)

    # Calculate speedup
    speedup = results["pytorch_avg_ms"] / results["tensorrt_avg_ms"]
    results["speedup"] = speedup

    logger.info("=" * 60)
    logger.info("Benchmark Results")
    logger.info("=" * 60)
    logger.info(f"PyTorch:   {results['pytorch_avg_ms']:.2f} ms (avg)")
    logger.info(f"           {results['pytorch_min_ms']:.2f} ms (min)")
    logger.info(f"           {results['pytorch_max_ms']:.2f} ms (max)")
    logger.info(f"TensorRT:  {results['tensorrt_avg_ms']:.2f} ms (avg)")
    logger.info(f"           {results['tensorrt_min_ms']:.2f} ms (min)")
    logger.info(f"           {results['tensorrt_max_ms']:.2f} ms (max)")
    logger.info(f"Speedup:   {speedup:.2f}x")
    logger.info("=" * 60)

    return results


def main() -> int:
    """Main entry point for the export script.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    parser = argparse.ArgumentParser(
        description="Export YOLOv8n-pose to TensorRT engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export with default settings
  python export_pose_tensorrt.py

  # Export specific model with FP32 precision
  python export_pose_tensorrt.py --model /models/yolov8n-pose.pt --precision fp32

  # Export and benchmark
  python export_pose_tensorrt.py --benchmark

  # Export to specific output
  python export_pose_tensorrt.py --output /models/pose_fp16.engine

Note:
  TensorRT engines are GPU-specific. Rebuild for each target GPU.
        """,
    )

    parser.add_argument(
        "--model",
        "-m",
        type=str,
        default=None,
        help="Path to YOLOv8n-pose model (default: from POSE_MODEL_PATH or /models/yolov8n-pose.pt)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Output path for TensorRT engine (default: same as model with .engine extension)",
    )
    parser.add_argument(
        "--precision",
        "-p",
        type=str,
        choices=["fp16", "fp32"],
        default="fp16",
        help="TensorRT precision (default: fp16)",
    )
    parser.add_argument(
        "--device",
        "-d",
        type=int,
        default=0,
        help="CUDA device index (default: 0)",
    )
    parser.add_argument(
        "--workspace",
        "-w",
        type=int,
        default=4,
        help="TensorRT workspace size in GB (default: 4)",
    )
    parser.add_argument(
        "--benchmark",
        "-b",
        action="store_true",
        help="Run benchmark after export",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only check requirements, don't export",
    )

    args = parser.parse_args()

    # Check requirements
    if not check_requirements():
        logger.error("Requirements check failed. Please install missing packages.")
        return 1

    if args.check_only:
        logger.info("Requirements check passed!")
        return 0

    # Get model path
    model_path = args.model or get_default_model_path()

    # Handle case where model doesn't exist but we can download it
    if not os.path.exists(model_path):
        if model_path == "yolov8n-pose.pt":
            logger.info("Model not found locally, will be downloaded from Ultralytics...")
        else:
            logger.error(f"Model file not found: {model_path}")
            logger.info("Hint: Set POSE_MODEL_PATH or use --model to specify the path")
            return 1

    try:
        # Export to TensorRT
        engine_path = export_to_tensorrt(
            model_path=model_path,
            output_path=args.output,
            precision=args.precision,
            device=args.device,
            workspace_gb=args.workspace,
            verbose=args.verbose,
        )

        # Run benchmark if requested
        if args.benchmark:
            benchmark_engines(
                pt_path=model_path,
                engine_path=engine_path,
                device=args.device,
            )

        return 0

    except Exception as e:
        logger.error(f"Export failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
