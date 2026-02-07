#!/usr/bin/env python3
"""Pre-build TensorRT engine during container build time (NEM-4999).

This script is executed during the Docker image build to convert the YOLO26m
PyTorch model (.pt) to a TensorRT engine (.engine). Pre-building eliminates
the cold-start latency that occurs when engines are built on first inference.

TensorRT engines are GPU-architecture-specific. The CUDA_COMPUTE_CAP build arg
controls which GPU architecture the engine targets:
  - sm_75: RTX 2080 / T4 / A400
  - sm_86: RTX 3090 / A5500
  - sm_89: RTX 4090 / L4
  - sm_90: H100

At container startup, the service validates that the pre-built engine matches
the runtime GPU. If there's a mismatch, it falls back to the existing runtime
rebuild mechanism (NEM-3871).

Usage (called from Dockerfile):
    python build_engine.py --model /models/yolo26/yolo26m.pt \
        --output /models/yolo26/exports/yolo26m_fp16.engine \
        --imgsz 640 --half

Environment Variables:
    CUDA_COMPUTE_CAP: Target GPU compute capability (default: auto-detect)
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


def get_gpu_compute_capability() -> str | None:
    """Get the compute capability of the current GPU.

    Returns:
        Compute capability string (e.g., '86' for sm_86), or None.
    """
    try:
        import torch

        if torch.cuda.is_available():
            props = torch.cuda.get_device_properties(0)
            return f"{props.major}{props.minor}"
    except Exception as e:
        logger.debug(f"Failed to detect GPU compute capability: {e}")
    return None


def build_tensorrt_engine(
    model_path: str,
    output_path: str,
    imgsz: int = 640,
    half: bool = True,
    dynamic: bool = False,
    workspace: int = 4,
) -> bool:
    """Build TensorRT engine from a PyTorch YOLO model.

    Args:
        model_path: Path to PyTorch .pt model.
        output_path: Path to write the TensorRT .engine file.
        imgsz: Input image size (default: 640).
        half: Use FP16 precision (default: True).
        dynamic: Enable dynamic batch size (default: False for build-time).
        workspace: TensorRT workspace size in GB (default: 4).

    Returns:
        True if engine was built successfully, False otherwise.
    """
    try:
        import torch
        from ultralytics import YOLO

        if not torch.cuda.is_available():
            logger.error("CUDA not available. Cannot build TensorRT engine.")
            return False

        gpu_name = torch.cuda.get_device_name(0)
        gpu_cc = get_gpu_compute_capability()
        logger.info(f"Building TensorRT engine on GPU: {gpu_name} (sm_{gpu_cc})")
        logger.info(f"  Model: {model_path}")
        logger.info(f"  Output: {output_path}")
        logger.info(f"  Image size: {imgsz}")
        logger.info(f"  FP16: {half}")
        logger.info(f"  Dynamic: {dynamic}")
        logger.info(f"  Workspace: {workspace}GB")

        # Ensure output directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # Load model
        model = YOLO(model_path)

        # Export to TensorRT
        start_time = time.time()
        exported_path = model.export(
            format="engine",
            imgsz=imgsz,
            half=half,
            device=0,
            dynamic=dynamic,
            simplify=True,
            workspace=workspace,
        )
        build_time = time.time() - start_time

        # Move to target location if needed
        exported_path_obj = Path(str(exported_path))
        target_path = Path(output_path)

        if exported_path_obj != target_path:
            import shutil

            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(exported_path_obj), str(target_path))

        engine_size_mb = target_path.stat().st_size / (1024 * 1024)
        logger.info(f"TensorRT engine built successfully in {build_time:.1f}s")
        logger.info(f"  Engine size: {engine_size_mb:.1f} MB")
        logger.info(f"  Engine path: {target_path}")

        # Write metadata file for startup validation
        _write_engine_metadata(str(target_path), gpu_cc, gpu_name, half)

        return True

    except Exception as e:
        logger.error(f"Failed to build TensorRT engine: {e}")
        return False


def _write_engine_metadata(
    engine_path: str,
    compute_cap: str | None,
    gpu_name: str | None,
    half: bool,
) -> None:
    """Write metadata file alongside the engine for startup validation.

    The metadata file allows the runtime startup check to verify that
    the pre-built engine matches the current GPU without loading the engine.

    Args:
        engine_path: Path to the TensorRT engine file.
        compute_cap: GPU compute capability (e.g., '86').
        gpu_name: GPU name string.
        half: Whether FP16 precision was used.
    """
    import json

    metadata = {
        "compute_capability": compute_cap,
        "gpu_name": gpu_name,
        "precision": "fp16" if half else "fp32",
        "build_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tensorrt_version": _get_tensorrt_version(),
    }

    metadata_path = engine_path + ".metadata.json"
    try:
        with open(Path(metadata_path).resolve(), "w") as f:  # nosemgrep: path-traversal-open
            json.dump(metadata, f, indent=2)
        logger.info(f"Engine metadata written to: {metadata_path}")
    except Exception:
        logger.warning("Failed to write engine metadata", exc_info=True)


def _get_tensorrt_version() -> str | None:
    """Get the installed TensorRT version."""
    try:
        import tensorrt as trt

        return str(trt.__version__)
    except ImportError:
        return None


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Pre-build TensorRT engine during container build (NEM-4999)",
    )
    parser.add_argument(
        "--model",
        type=str,
        required=True,
        help="Path to PyTorch model (.pt file)",
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Output path for TensorRT engine (.engine file)",
    )
    parser.add_argument(
        "--imgsz",
        type=int,
        default=640,
        help="Input image size (default: 640)",
    )
    parser.add_argument(
        "--half",
        action="store_true",
        default=True,
        help="Use FP16 precision (default: True)",
    )
    parser.add_argument(
        "--no-half",
        action="store_true",
        help="Disable FP16 precision (use FP32)",
    )
    parser.add_argument(
        "--dynamic",
        action="store_true",
        default=False,
        help="Enable dynamic batch size",
    )
    parser.add_argument(
        "--workspace",
        type=int,
        default=4,
        help="TensorRT workspace size in GB (default: 4)",
    )

    args = parser.parse_args()
    half = not args.no_half

    # Check if model exists
    if not Path(args.model).exists():
        logger.error(f"Model file not found: {args.model}")
        return 1

    success = build_tensorrt_engine(
        model_path=args.model,
        output_path=args.output,
        imgsz=args.imgsz,
        half=half,
        dynamic=args.dynamic,
        workspace=args.workspace,
    )

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
