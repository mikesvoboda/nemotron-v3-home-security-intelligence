#!/usr/bin/env python3
"""Pre-build TensorRT engine for CLIP vision encoder during container build (NEM-4999).

This script exports the CLIP vision encoder to ONNX and converts it to a TensorRT
engine during Docker image build. Pre-building eliminates the ~3-5 minute cold-start
latency on first inference when TensorRT auto-export runs at runtime.

TensorRT engines are GPU-architecture-specific. The engine built during image build
targets the GPU available at build time. At container startup, the service validates
that the pre-built engine matches the runtime GPU. If mismatched, it falls back to
the existing auto-export mechanism.

Usage (called from Dockerfile):
    python build_engine.py \
        --model-path /models/clip-vit-l \
        --output /cache/tensorrt/vision_encoder_fp16.engine \
        --precision fp16

Environment Variables:
    CLIP_MODEL_PATH: Path to HuggingFace CLIP model (default: /models/clip-vit-l)
"""

from __future__ import annotations

import argparse
import json
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


def get_gpu_info() -> tuple[str | None, str | None]:
    """Get GPU compute capability and name.

    Returns:
        Tuple of (compute_capability, gpu_name), either may be None.
    """
    try:
        import torch

        if torch.cuda.is_available():
            props = torch.cuda.get_device_properties(0)
            cc = f"{props.major}{props.minor}"
            name = torch.cuda.get_device_name(0)
            return cc, name
    except Exception as e:
        logger.debug(f"Failed to detect GPU: {e}")
    return None, None


def build_clip_tensorrt_engine(
    model_path: str,
    output_path: str,
    precision: str = "fp16",
    max_batch_size: int = 8,
    workspace_gb: int = 2,
) -> bool:
    """Build TensorRT engine for CLIP vision encoder.

    Pipeline:
    1. Load CLIP model from HuggingFace
    2. Export vision encoder to ONNX
    3. Convert ONNX to TensorRT engine

    Args:
        model_path: Path to HuggingFace CLIP model directory.
        output_path: Path to write the TensorRT engine file.
        precision: TensorRT precision ('fp16' or 'fp32').
        max_batch_size: Maximum batch size for dynamic batching.
        workspace_gb: TensorRT workspace size in GB.

    Returns:
        True if engine was built successfully, False otherwise.
    """
    try:
        import torch

        if not torch.cuda.is_available():
            logger.error("CUDA not available. Cannot build TensorRT engine.")
            return False

        gpu_cc, gpu_name = get_gpu_info()
        logger.info(f"Building CLIP TensorRT engine on GPU: {gpu_name} (sm_{gpu_cc})")
        logger.info(f"  Model: {model_path}")
        logger.info(f"  Output: {output_path}")
        logger.info(f"  Precision: {precision}")
        logger.info(f"  Max batch: {max_batch_size}")
        logger.info(f"  Workspace: {workspace_gb}GB")

        output_path_obj = Path(output_path)
        output_dir = output_path_obj.parent
        output_dir.mkdir(parents=True, exist_ok=True)

        onnx_path = output_dir / "vision_encoder.onnx"

        # Step 1: Export to ONNX
        from export_onnx import CLIPVisionONNXExporter, convert_to_tensorrt

        logger.info("Step 1/2: Exporting CLIP vision encoder to ONNX...")
        start_time = time.time()

        exporter = CLIPVisionONNXExporter(model_path=model_path)
        exporter.load_model()
        exporter.export(
            output_path=str(onnx_path),
            dynamic_batch=True,
            max_batch_size=max_batch_size,
        )

        onnx_time = time.time() - start_time
        logger.info(f"ONNX export complete in {onnx_time:.1f}s: {onnx_path}")

        # Step 2: Convert to TensorRT
        logger.info(f"Step 2/2: Converting ONNX to TensorRT {precision.upper()}...")
        start_time = time.time()

        convert_to_tensorrt(
            onnx_path=str(onnx_path),
            output_path=str(output_path_obj),
            precision=precision,
            max_batch_size=max_batch_size,
            workspace_gb=workspace_gb,
        )

        trt_time = time.time() - start_time
        engine_size_mb = output_path_obj.stat().st_size / (1024 * 1024)

        logger.info(f"TensorRT engine built in {trt_time:.1f}s")
        logger.info(f"  Engine size: {engine_size_mb:.1f} MB")
        logger.info(f"  Engine path: {output_path_obj}")

        # Write metadata for startup validation
        _write_engine_metadata(str(output_path_obj), gpu_cc, gpu_name, precision)

        # Clean up ONNX file to save image space
        if onnx_path.exists():
            onnx_path.unlink()
            logger.info(f"Cleaned up intermediate ONNX file: {onnx_path}")

        return True

    except ImportError as e:
        logger.error(f"Missing dependency for TensorRT export: {e}")
        return False
    except Exception as e:
        logger.error(f"Failed to build CLIP TensorRT engine: {e}")
        return False


def _write_engine_metadata(
    engine_path: str,
    compute_cap: str | None,
    gpu_name: str | None,
    precision: str,
) -> None:
    """Write metadata file alongside the engine for startup validation."""
    trt_version = None
    try:
        import tensorrt as trt

        trt_version = str(trt.__version__)
    except ImportError:
        pass

    metadata = {
        "compute_capability": compute_cap,
        "gpu_name": gpu_name,
        "precision": precision,
        "build_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tensorrt_version": trt_version,
        "model_type": "clip-vit-l-vision-encoder",
    }

    metadata_path = engine_path + ".metadata.json"
    try:
        with open(Path(metadata_path).resolve(), "w") as f:  # nosemgrep: path-traversal-open
            json.dump(metadata, f, indent=2)
        logger.info(f"Engine metadata written to: {metadata_path}")
    except Exception as e:
        logger.warning(f"Failed to write engine metadata: {e}")


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Pre-build CLIP TensorRT engine during container build (NEM-4999)",
    )
    parser.add_argument(
        "--model-path",
        type=str,
        default=os.environ.get("CLIP_MODEL_PATH", "/models/clip-vit-l"),
        help="Path to HuggingFace CLIP model directory",
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Output path for TensorRT engine (.engine file)",
    )
    parser.add_argument(
        "--precision",
        choices=["fp16", "fp32"],
        default="fp16",
        help="TensorRT precision (default: fp16)",
    )
    parser.add_argument(
        "--max-batch",
        type=int,
        default=8,
        help="Maximum batch size for dynamic batching (default: 8)",
    )
    parser.add_argument(
        "--workspace",
        type=int,
        default=2,
        help="TensorRT workspace size in GB (default: 2)",
    )

    args = parser.parse_args()

    # Check if model exists
    if not Path(args.model_path).exists():
        logger.error(f"CLIP model not found: {args.model_path}")
        logger.info("Skipping TensorRT pre-build (model will be loaded at runtime)")
        return 0  # Non-fatal: model may be mounted at runtime

    success = build_clip_tensorrt_engine(
        model_path=args.model_path,
        output_path=args.output,
        precision=args.precision,
        max_batch_size=args.max_batch,
        workspace_gb=args.workspace,
    )

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
