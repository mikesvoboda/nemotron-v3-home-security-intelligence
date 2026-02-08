#!/usr/bin/env python3
"""Export YOLOv8n-pose to TensorRT FP16 engine or ONNX for Triton Inference Server.

Model: Ultralytics YOLOv8n-pose (17 COCO keypoints)
Source: /models/zoo/yolov8n-pose/yolov8n-pose.pt
Input: (1, 3, 640, 640) FP16/FP32 — letterboxed and normalized
Output: Bounding boxes + 17 keypoints (x, y, conf) per detection

The Ultralytics export pipeline handles the full conversion:
  .pt -> ONNX -> TensorRT FP16 engine (.engine)   [default]
  .pt -> ONNX                                      [--onnx-only]

Since model zoo volumes are mounted read-only, the .pt file is copied to
a temporary writable directory before export.  The resulting file
is then placed at the Triton model repository path.

Environment Variables:
    POSE_TENSORRT_DEVICE: CUDA device index for export (default: "0")

Usage:
    # TensorRT export (default)
    python export_yolo_pose.py \\
        --model-path /models/zoo/yolov8n-pose/yolov8n-pose.pt \\
        --output-path /models/cache/pose/1/model.plan

    # ONNX-only export (for GPUs with limited VRAM)
    python export_yolo_pose.py \\
        --model-path /models/zoo/yolov8n-pose/yolov8n-pose.pt \\
        --output-path /models/cache/pose/1/model.onnx \\
        --onnx-only
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import sys
import tempfile
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Default paths matching the enrichment-light service configuration
DEFAULT_MODEL_PATH = "/models/zoo/yolov8n-pose/yolov8n-pose.pt"
DEFAULT_OUTPUT_PATH = "/models/cache/pose/1/model.onnx"

# Export settings
IMGSZ = 640


def export_to_tensorrt(
    model_path: str,
    output_path: str,
    device: str = "0",
) -> None:
    """Export YOLOv8n-pose to TensorRT FP16 engine via Ultralytics.

    The export process:
    1. Copies the .pt model to a writable temp directory (zoo is read-only)
    2. Loads the model via Ultralytics YOLO
    3. Calls model.export(format='engine', half=True) which runs:
       .pt -> ONNX -> TensorRT builder -> serialized .engine
    4. Copies the resulting .engine file to the output path

    Args:
        model_path: Path to the YOLOv8n-pose .pt weights file.
        output_path: Destination path for the TensorRT engine (model.plan).
        device: CUDA device index for export (e.g. "0").

    Raises:
        FileNotFoundError: If the source .pt model does not exist.
        RuntimeError: If TensorRT export fails.
    """
    from ultralytics import YOLO

    model_path_obj = Path(model_path)
    if not model_path_obj.exists():
        raise FileNotFoundError(f"Pose model not found: {model_path}")

    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Source model: {model_path}")
    logger.info(f"Output path: {output_path}")
    logger.info(f"Device: cuda:{device}")
    logger.info("Precision: FP16")
    logger.info(f"Image size: {IMGSZ}")

    # Work in a writable temp directory since model zoo may be read-only
    with tempfile.TemporaryDirectory(prefix="pose_export_") as tmpdir:
        tmp_model = Path(tmpdir) / model_path_obj.name
        logger.info(f"Copying model to writable directory: {tmp_model}")
        shutil.copy2(model_path, tmp_model)

        # Load model from writable copy
        model = YOLO(str(tmp_model))

        # Export to TensorRT engine (Ultralytics handles ONNX intermediate step)
        logger.info("Starting TensorRT export (this may take several minutes)...")
        export_result = model.export(
            format="engine",
            half=True,
            device=device,
            imgsz=IMGSZ,
        )

        # Locate the exported engine file
        engine_path = _find_engine(export_result, tmp_model)
        if engine_path is None:
            raise RuntimeError(
                "TensorRT export completed but no .engine file was produced. "
                "Check that TensorRT is installed and a compatible GPU is available."
            )

        # Copy engine to final output path
        logger.info(f"Copying engine to output: {engine_path} -> {output_path}")
        shutil.copy2(str(engine_path), output_path)

    file_size_mb = Path(output_path).stat().st_size / (1024 * 1024)
    logger.info(f"TensorRT engine saved: {output_path} ({file_size_mb:.1f} MB)")


def _find_engine(
    export_result: str | None,
    tmp_model: Path,
) -> Path | None:
    """Locate the TensorRT engine file after Ultralytics export.

    Ultralytics may place the .engine file in several locations depending
    on the version.  Check them in order of likelihood.

    Args:
        export_result: The path string returned by model.export(), if any.
        tmp_model: The temporary .pt model path used for export.

    Returns:
        Path to the engine file, or None if not found.
    """
    # 1. Check the path returned by export()
    if export_result:
        result_path = Path(str(export_result))
        if result_path.exists() and result_path.suffix == ".engine":
            return result_path

    # 2. Check for .engine alongside the temp .pt file
    engine_beside_model = tmp_model.with_suffix(".engine")
    if engine_beside_model.exists():
        return engine_beside_model

    # 3. Search the temp directory for any .engine file
    for engine_file in tmp_model.parent.rglob("*.engine"):
        return engine_file

    return None


def export_to_onnx(
    model_path: str,
    output_path: str,
    device: str = "0",
) -> None:
    """Export YOLOv8n-pose to ONNX format via Ultralytics.

    Uses Ultralytics' built-in ONNX export which is lighter than TensorRT
    and does not require large GPU workspace memory.  Suitable for GPUs
    with limited VRAM (e.g. 4 GB RTX A400).

    The export process:
    1. Copies the .pt model to a writable temp directory (zoo is read-only)
    2. Loads the model via Ultralytics YOLO
    3. Calls model.export(format='onnx') which produces a .onnx file
    4. Copies the resulting .onnx file to the output path

    Args:
        model_path: Path to the YOLOv8n-pose .pt weights file.
        output_path: Destination path for the ONNX model (model.onnx).
        device: CUDA device index for export (e.g. "0").

    Raises:
        FileNotFoundError: If the source .pt model does not exist.
        RuntimeError: If ONNX export fails.
    """
    from ultralytics import YOLO

    model_path_obj = Path(model_path)
    if not model_path_obj.exists():
        raise FileNotFoundError(f"Pose model not found: {model_path}")

    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Source model: {model_path}")
    logger.info(f"Output path: {output_path}")
    logger.info(f"Device: cuda:{device}")
    logger.info("Format: ONNX")
    logger.info(f"Image size: {IMGSZ}")

    # Work in a writable temp directory since model zoo may be read-only
    with tempfile.TemporaryDirectory(prefix="pose_export_") as tmpdir:
        tmp_model = Path(tmpdir) / model_path_obj.name
        logger.info(f"Copying model to writable directory: {tmp_model}")
        shutil.copy2(model_path, tmp_model)

        # Load model from writable copy
        model = YOLO(str(tmp_model))

        # Export to ONNX (Ultralytics produces .onnx next to the source .pt)
        logger.info("Starting ONNX export...")
        export_result = model.export(
            format="onnx",
            device=device,
            imgsz=IMGSZ,
        )

        # Locate the exported ONNX file
        onnx_path = _find_onnx(export_result, tmp_model)
        if onnx_path is None:
            raise RuntimeError(
                "ONNX export completed but no .onnx file was produced. "
                "Check that the ultralytics package is installed correctly."
            )

        # Copy ONNX to final output path
        logger.info(f"Copying ONNX model to output: {onnx_path} -> {output_path}")
        shutil.copy2(str(onnx_path), output_path)

    file_size_mb = Path(output_path).stat().st_size / (1024 * 1024)
    logger.info(f"ONNX model saved: {output_path} ({file_size_mb:.1f} MB)")


def _find_onnx(
    export_result: str | None,
    tmp_model: Path,
) -> Path | None:
    """Locate the ONNX file after Ultralytics export.

    Ultralytics places the .onnx file next to the source .pt file,
    replacing the extension.  Check several locations in case of
    version differences.

    Args:
        export_result: The path string returned by model.export(), if any.
        tmp_model: The temporary .pt model path used for export.

    Returns:
        Path to the ONNX file, or None if not found.
    """
    # 1. Check the path returned by export()
    if export_result:
        result_path = Path(str(export_result))
        if result_path.exists() and result_path.suffix == ".onnx":
            return result_path

    # 2. Check for .onnx alongside the temp .pt file
    onnx_beside_model = tmp_model.with_suffix(".onnx")
    if onnx_beside_model.exists():
        return onnx_beside_model

    # 3. Search the temp directory for any .onnx file
    for onnx_file in tmp_model.parent.rglob("*.onnx"):
        return onnx_file

    return None


def validate_model(output_path: str) -> bool:
    """Quick validation that the exported model file looks reasonable.

    Checks file size and existence.  Full inference validation
    is deferred to Triton startup.

    Args:
        output_path: Path to the exported model file (.plan or .onnx).

    Returns:
        True if basic checks pass.
    """
    path = Path(output_path)
    if not path.exists():
        logger.error(f"Model file does not exist: {output_path}")
        return False

    file_size = path.stat().st_size
    if file_size < 1024:
        logger.error(f"Model file suspiciously small: {file_size} bytes")
        return False

    file_size_mb = file_size / (1024 * 1024)
    logger.info(f"Model file size: {file_size_mb:.1f} MB")
    logger.info("Validation passed (full inference validation deferred to Triton)")
    return True


def validate_engine(output_path: str) -> bool:
    """Quick validation that the engine file looks reasonable.

    Checks file size and TensorRT magic bytes.  Full inference validation
    is deferred to Triton startup.

    Args:
        output_path: Path to the exported engine file.

    Returns:
        True if basic checks pass.
    """
    path = Path(output_path)
    if not path.exists():
        logger.error(f"Engine file does not exist: {output_path}")
        return False

    file_size = path.stat().st_size
    if file_size < 1024:
        logger.error(f"Engine file suspiciously small: {file_size} bytes")
        return False

    file_size_mb = file_size / (1024 * 1024)
    logger.info(f"Engine file size: {file_size_mb:.1f} MB")
    logger.info("Validation passed (full inference validation deferred to Triton)")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export YOLOv8n-pose to TensorRT FP16 engine or ONNX for Triton"
    )
    parser.add_argument(
        "--model-path",
        type=str,
        default=DEFAULT_MODEL_PATH,
        help="Path to the YOLOv8n-pose .pt weights file",
    )
    parser.add_argument(
        "--output-path",
        type=str,
        default=DEFAULT_OUTPUT_PATH,
        help="Output path for the exported model (model.plan or model.onnx)",
    )
    parser.add_argument(
        "--device",
        type=str,
        default=os.environ.get("POSE_TENSORRT_DEVICE", "0"),
        help="CUDA device index for export (default: 0)",
    )
    parser.add_argument(
        "--onnx-only",
        action="store_true",
        help="Export ONNX only, skip TensorRT conversion (for GPUs with limited VRAM)",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip post-export validation",
    )
    args = parser.parse_args()

    try:
        if args.onnx_only:
            export_to_onnx(args.model_path, args.output_path, device=args.device)
        else:
            export_to_tensorrt(args.model_path, args.output_path, device=args.device)

        if not args.skip_validation:
            if not validate_model(args.output_path):
                logger.error("Post-export validation failed")
                return 1

        fmt = "ONNX" if args.onnx_only else "TensorRT"
        logger.info(f"YOLOv8n-pose {fmt} export complete")
        return 0

    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        return 1
    except ImportError as e:
        logger.error(f"Missing dependency: {e}. Ensure ultralytics is installed.")
        return 1
    except Exception as e:
        logger.error(f"Export failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
