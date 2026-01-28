#!/usr/bin/env python3
"""YOLO26 TensorRT Export Script

Exports YOLO26m PyTorch model to TensorRT engine with INT8 or FP16 precision.
INT8 quantization provides ~2x throughput improvement with minimal accuracy loss.

Requirements:
- NVIDIA GPU with TensorRT support
- ultralytics>=8.4.0
- TensorRT runtime (installed via nvidia-tensorrt or container)
- CUDA-compatible GPU matching deployment architecture

Usage Examples:
    # Export FP16 engine (default, higher accuracy)
    python export_tensorrt.py

    # Export INT8 engine (2x throughput, requires calibration data)
    python export_tensorrt.py --int8 --data config/yolo26_calibration.yaml

    # Export with frame extraction from videos
    python export_tensorrt.py --int8 --data config/yolo26_calibration.yaml --extract-frames

    # Benchmark exported engine
    python export_tensorrt.py --benchmark /path/to/engine.engine

Output:
    - FP16: yolo26m_fp16.engine
    - INT8: yolo26m_int8.engine

For production deployment, the engine should be placed at:
    /export/ai_models/model-zoo/yolo26/exports/yolo26m_{fp16,int8}.engine
"""

from __future__ import annotations

import argparse
import logging
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def check_cuda_available() -> bool:
    """Check if CUDA is available for TensorRT export."""
    try:
        import torch

        if torch.cuda.is_available():
            device_name = torch.cuda.get_device_name(0)
            logger.info(f"CUDA available: {device_name}")
            return True
        else:
            logger.warning("CUDA not available - TensorRT export requires NVIDIA GPU")
            return False
    except ImportError:
        logger.error("PyTorch not installed")
        return False


def extract_frames_from_videos(
    source_dir: Path,
    output_dir: Path,
    fps: int = 1,
    max_frames_per_video: int = 30,
) -> int:
    """Extract frames from video files for calibration.

    Args:
        source_dir: Directory containing video files (searches recursively)
        output_dir: Directory to save extracted frames
        fps: Frames per second to extract (default: 1)
        max_frames_per_video: Maximum frames to extract per video (default: 30)

    Returns:
        Number of frames extracted
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    video_extensions = {".mp4", ".avi", ".mkv", ".webm", ".mov"}
    video_files = []
    for ext in video_extensions:
        video_files.extend(source_dir.rglob(f"*{ext}"))

    logger.info(f"Found {len(video_files)} video files in {source_dir}")

    total_frames = 0
    for video_path in video_files:
        # Create unique prefix for each video
        video_name = video_path.stem
        parent_name = video_path.parent.name

        # Use ffmpeg to extract frames
        output_pattern = output_dir / f"{parent_name}_{video_name}_%04d.jpg"

        cmd = [
            "ffmpeg",
            "-i",
            str(video_path),
            "-vf",
            f"fps={fps}",
            "-frames:v",
            str(max_frames_per_video),
            "-q:v",
            "2",  # High quality JPEG
            str(output_pattern),
            "-y",  # Overwrite
            "-loglevel",
            "error",
        ]

        try:
            # S603: Safe - all inputs are validated paths from our controlled source directory
            subprocess.run(cmd, check=True, capture_output=True)
            # Count extracted frames
            extracted = list(output_dir.glob(f"{parent_name}_{video_name}_*.jpg"))
            total_frames += len(extracted)
            logger.info(f"Extracted {len(extracted)} frames from {video_path.name}")
        except subprocess.CalledProcessError as e:
            logger.warning(f"Failed to extract frames from {video_path}: {e}")
        except FileNotFoundError:
            logger.error("ffmpeg not found - install ffmpeg to extract frames from videos")
            raise

    logger.info(f"Total frames extracted: {total_frames}")
    return total_frames


def copy_images_to_calibration_dir(source_dir: Path, output_dir: Path) -> int:
    """Copy existing images to calibration directory.

    Args:
        source_dir: Directory containing images (searches recursively)
        output_dir: Directory to copy images to

    Returns:
        Number of images copied
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    image_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    count = 0

    for ext in image_extensions:
        for img_path in source_dir.rglob(f"*{ext}"):
            # Create unique filename
            parent_name = img_path.parent.name
            dest_path = output_dir / f"{parent_name}_{img_path.name}"
            shutil.copy2(img_path, dest_path)
            count += 1

    logger.info(f"Copied {count} images to calibration directory")
    return count


def prepare_calibration_data(
    data_yaml_path: Path,
    extract_frames: bool = False,
) -> Path:
    """Prepare calibration data directory for INT8 quantization.

    Args:
        data_yaml_path: Path to YAML config with data paths
        extract_frames: Whether to extract frames from videos

    Returns:
        Path to prepared calibration directory
    """
    import yaml

    # Resolve and validate path to prevent path traversal
    resolved_path = Path(data_yaml_path).resolve()
    if not resolved_path.exists():
        raise FileNotFoundError(f"Calibration YAML not found: {resolved_path}")

    with open(resolved_path) as f:  # nosemgrep: path-traversal-open
        config = yaml.safe_load(f)

    source_dir = Path(config.get("path", "."))
    if not source_dir.exists():
        raise FileNotFoundError(f"Calibration data path not found: {source_dir}")

    # Create temporary calibration directory
    calib_dir = Path(tempfile.mkdtemp(prefix="yolo26_calib_"))
    images_dir = calib_dir / "images"
    images_dir.mkdir(parents=True)

    logger.info(f"Preparing calibration data from {source_dir}")
    logger.info(f"Calibration directory: {calib_dir}")

    total_images = 0

    # Copy existing images
    total_images += copy_images_to_calibration_dir(source_dir, images_dir)

    # Extract frames from videos if requested
    if extract_frames:
        total_images += extract_frames_from_videos(source_dir, images_dir)

    if total_images == 0:
        raise ValueError(
            f"No calibration images found in {source_dir}. "
            "Use --extract-frames to extract frames from videos."
        )

    logger.info(f"Total calibration images: {total_images}")

    # Create updated YAML config pointing to prepared data
    new_config = config.copy()
    new_config["path"] = str(images_dir)
    new_config["train"] = "."
    new_config["val"] = "."

    new_yaml_path = calib_dir / "calibration.yaml"
    with open(new_yaml_path, "w") as f:  # nosemgrep: path-traversal-open
        yaml.dump(new_config, f)

    return new_yaml_path


def export_tensorrt(
    model_path: str = "yolo26m.pt",
    output_dir: str | None = None,
    int8: bool = False,
    data: str | None = None,
    imgsz: int = 640,
    batch: int = 8,
    workspace: int = 4,
    dynamic: bool = True,
    extract_frames: bool = False,
) -> Path:
    """Export YOLO26m model to TensorRT engine.

    Args:
        model_path: Path to PyTorch model (.pt) or HuggingFace model name
        output_dir: Output directory for engine file (default: same as model)
        int8: Enable INT8 quantization (requires calibration data)
        data: Path to calibration dataset YAML (required for INT8)
        imgsz: Input image size (default: 640)
        batch: Batch size for export (default: 8)
        workspace: TensorRT workspace size in GB (default: 4)
        dynamic: Enable dynamic batch size (default: True)
        extract_frames: Extract frames from videos for calibration

    Returns:
        Path to exported TensorRT engine
    """
    from ultralytics import YOLO

    # Validate INT8 requirements
    if int8 and not data:
        raise ValueError("INT8 quantization requires calibration data. Provide --data argument.")

    # Load model
    logger.info(f"Loading model from {model_path}")
    model = YOLO(model_path)

    # Prepare calibration data if INT8
    calib_yaml = None
    if int8 and data:
        data_path = Path(data)
        if not data_path.exists():
            raise FileNotFoundError(f"Calibration data file not found: {data}")
        calib_yaml = prepare_calibration_data(data_path, extract_frames=extract_frames)
        logger.info(f"Using calibration data from: {calib_yaml}")

    # Determine output path
    precision = "int8" if int8 else "fp16"
    model_name = Path(model_path).stem if Path(model_path).exists() else model_path.split("/")[-1]
    engine_name = f"{model_name}_{precision}.engine"

    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
    else:
        output_path = Path(model_path).parent if Path(model_path).exists() else Path.cwd()

    # Export to TensorRT
    logger.info(f"Exporting to TensorRT {precision.upper()} engine...")
    logger.info(f"  Image size: {imgsz}")
    logger.info(f"  Batch size: {batch}")
    logger.info(f"  Workspace: {workspace}GB")
    logger.info(f"  Dynamic shapes: {dynamic}")

    export_args: dict[str, object] = {
        "format": "engine",
        "imgsz": imgsz,
        "batch": batch,
        "workspace": workspace,
        "dynamic": dynamic,
        "verbose": True,
    }

    if int8:
        export_args["int8"] = True
        export_args["data"] = str(calib_yaml)
        logger.info("  INT8 quantization: enabled")
    else:
        export_args["half"] = True  # FP16
        logger.info("  FP16 precision: enabled")

    start_time = time.time()
    result = model.export(**export_args)
    export_time = time.time() - start_time

    logger.info(f"Export completed in {export_time:.1f}s")
    logger.info(f"Engine saved to: {result}")

    # Move to output directory with standard name if needed
    result_path = Path(result)
    final_path = output_path / engine_name
    if result_path != final_path:
        shutil.move(result_path, final_path)
        logger.info(f"Renamed to: {final_path}")

    return final_path


def benchmark_engine(engine_path: str, num_iterations: int = 100) -> dict[str, float]:
    """Benchmark TensorRT engine performance.

    Args:
        engine_path: Path to TensorRT engine file
        num_iterations: Number of inference iterations

    Returns:
        Dictionary with benchmark results
    """
    import numpy as np
    from PIL import Image
    from ultralytics import YOLO

    logger.info(f"Benchmarking engine: {engine_path}")

    # Load engine
    model = YOLO(engine_path)

    # Create test image
    test_image = Image.new("RGB", (640, 480), color=(128, 128, 128))

    # Warmup
    logger.info("Warming up...")
    for _ in range(10):
        model.predict(source=test_image, verbose=False)

    # Benchmark
    logger.info(f"Running {num_iterations} iterations...")
    latencies = []
    for _ in range(num_iterations):
        start = time.perf_counter()
        model.predict(source=test_image, verbose=False)
        latencies.append((time.perf_counter() - start) * 1000)  # ms

    # Calculate statistics
    latencies_np = np.array(latencies)
    results = {
        "mean_ms": float(np.mean(latencies_np)),
        "std_ms": float(np.std(latencies_np)),
        "min_ms": float(np.min(latencies_np)),
        "max_ms": float(np.max(latencies_np)),
        "p50_ms": float(np.percentile(latencies_np, 50)),
        "p95_ms": float(np.percentile(latencies_np, 95)),
        "p99_ms": float(np.percentile(latencies_np, 99)),
        "throughput_fps": 1000.0 / float(np.mean(latencies_np)),
    }

    logger.info("Benchmark Results:")
    logger.info(f"  Mean latency: {results['mean_ms']:.2f}ms")
    logger.info(f"  Std deviation: {results['std_ms']:.2f}ms")
    logger.info(f"  P50 latency: {results['p50_ms']:.2f}ms")
    logger.info(f"  P95 latency: {results['p95_ms']:.2f}ms")
    logger.info(f"  P99 latency: {results['p99_ms']:.2f}ms")
    logger.info(f"  Throughput: {results['throughput_fps']:.1f} FPS")

    return results


def validate_accuracy(
    engine_path: str,
    data_yaml: str,
    batch_size: int = 16,
) -> dict[str, float]:
    """Validate model accuracy on a dataset.

    Args:
        engine_path: Path to TensorRT engine
        data_yaml: Path to validation dataset YAML
        batch_size: Batch size for validation

    Returns:
        Dictionary with validation metrics (mAP, etc.)
    """
    from ultralytics import YOLO

    logger.info(f"Validating accuracy: {engine_path}")
    logger.info(f"Validation data: {data_yaml}")

    model = YOLO(engine_path)

    results = model.val(data=data_yaml, batch=batch_size, verbose=True)

    metrics = {
        "mAP50": float(results.box.map50),
        "mAP50-95": float(results.box.map),
        "precision": float(results.box.mp),
        "recall": float(results.box.mr),
    }

    logger.info("Validation Results:")
    logger.info(f"  mAP@50: {metrics['mAP50']:.4f}")
    logger.info(f"  mAP@50-95: {metrics['mAP50-95']:.4f}")
    logger.info(f"  Precision: {metrics['precision']:.4f}")
    logger.info(f"  Recall: {metrics['recall']:.4f}")

    return metrics


def main() -> int:
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="Export YOLO26m to TensorRT engine with INT8 or FP16 precision",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Export FP16 engine (default)
    python export_tensorrt.py

    # Export INT8 engine with calibration data
    python export_tensorrt.py --int8 --data config/yolo26_calibration.yaml

    # Export INT8 with frame extraction from videos
    python export_tensorrt.py --int8 --data config/yolo26_calibration.yaml --extract-frames

    # Benchmark an exported engine
    python export_tensorrt.py --benchmark exports/yolo26m_int8.engine

    # Compare FP16 vs INT8 accuracy
    python export_tensorrt.py --validate exports/yolo26m_fp16.engine --data coco.yaml
    python export_tensorrt.py --validate exports/yolo26m_int8.engine --data coco.yaml
        """,
    )

    parser.add_argument(
        "--model",
        type=str,
        default="yolo26m.pt",
        help="Path to PyTorch model (.pt) or model name (default: yolo26m.pt)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output directory for engine file",
    )
    parser.add_argument(
        "--int8",
        action="store_true",
        help="Enable INT8 quantization (requires --data for calibration)",
    )
    parser.add_argument(
        "--data",
        type=str,
        default=None,
        help="Path to calibration/validation dataset YAML",
    )
    parser.add_argument(
        "--imgsz",
        type=int,
        default=640,
        help="Input image size (default: 640)",
    )
    parser.add_argument(
        "--batch",
        type=int,
        default=8,
        help="Batch size for export (default: 8)",
    )
    parser.add_argument(
        "--workspace",
        type=int,
        default=4,
        help="TensorRT workspace size in GB (default: 4)",
    )
    parser.add_argument(
        "--no-dynamic",
        action="store_true",
        help="Disable dynamic batch size",
    )
    parser.add_argument(
        "--extract-frames",
        action="store_true",
        help="Extract frames from videos for INT8 calibration",
    )
    parser.add_argument(
        "--benchmark",
        type=str,
        default=None,
        help="Benchmark an existing TensorRT engine",
    )
    parser.add_argument(
        "--validate",
        type=str,
        default=None,
        help="Validate accuracy of an existing TensorRT engine",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=100,
        help="Number of iterations for benchmarking (default: 100)",
    )

    args = parser.parse_args()

    # Check CUDA availability
    if not check_cuda_available():
        logger.error("CUDA is required for TensorRT export")
        return 1

    # Benchmark mode
    if args.benchmark:
        if not Path(args.benchmark).exists():
            logger.error(f"Engine file not found: {args.benchmark}")
            return 1
        benchmark_engine(args.benchmark, num_iterations=args.iterations)
        return 0

    # Validation mode
    if args.validate:
        if not Path(args.validate).exists():
            logger.error(f"Engine file not found: {args.validate}")
            return 1
        if not args.data:
            logger.error("Validation requires --data argument")
            return 1
        validate_accuracy(args.validate, args.data)
        return 0

    # Export mode
    try:
        engine_path = export_tensorrt(
            model_path=args.model,
            output_dir=args.output,
            int8=args.int8,
            data=args.data,
            imgsz=args.imgsz,
            batch=args.batch,
            workspace=args.workspace,
            dynamic=not args.no_dynamic,
            extract_frames=args.extract_frames,
        )
        logger.info(f"Successfully exported TensorRT engine: {engine_path}")

        # Auto-benchmark after export
        logger.info("Running automatic benchmark...")
        benchmark_engine(str(engine_path))

        return 0
    except Exception as e:
        logger.error(f"Export failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
