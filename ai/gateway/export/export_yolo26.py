#!/usr/bin/env python3
"""Export YOLO26m to ONNX for Triton Inference Server.

Model: Ultralytics YOLO26m (80 COCO object detection classes)
Source: /models/zoo/yolo26/yolo26m.pt
Input: (1, 3, 640, 640) FP32 -- letterboxed and normalized
Output: (1, 84, 8400) FP32 -- raw YOLO detections (4 box + 80 class scores)

The Ultralytics export pipeline handles the full conversion:
  .pt -> ONNX                                      [default / --onnx-only]
  .pt -> ONNX -> TensorRT FP16 engine (.engine)    [--tensorrt]

ONNX is the default because the RTX A400 (4 GB) does not have enough
workspace memory for TensorRT engine building.  The ONNX Runtime with
CUDA EP provides near-TensorRT performance for this model size.

Since model zoo volumes are mounted read-only, the .pt file is copied to
a temporary writable directory before export.  The resulting file is then
placed at the Triton model cache path.

Environment Variables:
    YOLO26_EXPORT_DEVICE: CUDA device index for export (default: "0")

Usage:
    # ONNX export (default)
    python export_yolo26.py \\
        --model-path /models/zoo/yolo26/yolo26m.pt \\
        --output-path /models/cache/yolo26/1/model.onnx

    # TensorRT export (requires >4 GB VRAM)
    python export_yolo26.py \\
        --model-path /models/zoo/yolo26/yolo26m.pt \\
        --output-path /models/cache/yolo26/1/model.plan \\
        --tensorrt
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

# Default paths matching the YOLO26 service configuration
DEFAULT_MODEL_PATH = "/models/zoo/yolo26/yolo26m.pt"
DEFAULT_OUTPUT_PATH = "/models/cache/yolo26/1/model.onnx"

# Export settings
IMGSZ = 640


def export_to_onnx(
    model_path: str,
    output_path: str,
    device: str = "0",
) -> None:
    """Export YOLO26m to ONNX format via Ultralytics.

    Uses Ultralytics' built-in ONNX export which is lighter than TensorRT
    and does not require large GPU workspace memory.  Suitable for GPUs
    with limited VRAM (e.g. 4 GB RTX A400).

    The export process:
    1. Copies the .pt model to a writable temp directory (zoo is read-only)
    2. Loads the model via Ultralytics YOLO
    3. Calls model.export(format='onnx') which produces a .onnx file
    4. Copies the resulting .onnx file to the output path

    Args:
        model_path: Path to the YOLO26m .pt weights file.
        output_path: Destination path for the ONNX model (model.onnx).
        device: CUDA device index for export (e.g. "0").

    Raises:
        FileNotFoundError: If the source .pt model does not exist.
        RuntimeError: If ONNX export fails.
    """
    from ultralytics import YOLO

    model_path_obj = Path(model_path)
    if not model_path_obj.exists():
        raise FileNotFoundError(f"YOLO26 model not found: {model_path}")

    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Source model: {model_path}")
    logger.info(f"Output path: {output_path}")
    logger.info(f"Device: cuda:{device}")
    logger.info("Format: ONNX")
    logger.info(f"Image size: {IMGSZ}")

    # Work in a writable temp directory since model zoo may be read-only
    with tempfile.TemporaryDirectory(prefix="yolo26_export_") as tmpdir:
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


def export_to_tensorrt(
    model_path: str,
    output_path: str,
    device: str = "0",
) -> None:
    """Export YOLO26m to TensorRT FP16 engine via Ultralytics.

    The export process:
    1. Copies the .pt model to a writable temp directory (zoo is read-only)
    2. Loads the model via Ultralytics YOLO
    3. Calls model.export(format='engine', half=True) which runs:
       .pt -> ONNX -> TensorRT builder -> serialized .engine
    4. Copies the resulting .engine file to the output path

    Args:
        model_path: Path to the YOLO26m .pt weights file.
        output_path: Destination path for the TensorRT engine (model.plan).
        device: CUDA device index for export (e.g. "0").

    Raises:
        FileNotFoundError: If the source .pt model does not exist.
        RuntimeError: If TensorRT export fails.
    """
    from ultralytics import YOLO

    model_path_obj = Path(model_path)
    if not model_path_obj.exists():
        raise FileNotFoundError(f"YOLO26 model not found: {model_path}")

    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Source model: {model_path}")
    logger.info(f"Output path: {output_path}")
    logger.info(f"Device: cuda:{device}")
    logger.info("Precision: FP16")
    logger.info(f"Image size: {IMGSZ}")

    # Work in a writable temp directory since model zoo may be read-only
    with tempfile.TemporaryDirectory(prefix="yolo26_export_") as tmpdir:
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


def _find_engine(
    export_result: str | None,
    tmp_model: Path,
) -> Path | None:
    """Locate the TensorRT engine file after Ultralytics export.

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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export YOLO26m to ONNX or TensorRT for Triton Inference Server"
    )
    parser.add_argument(
        "--model-path",
        type=str,
        default=DEFAULT_MODEL_PATH,
        help="Path to the YOLO26m .pt weights file",
    )
    parser.add_argument(
        "--output-path",
        type=str,
        default=DEFAULT_OUTPUT_PATH,
        help="Output path for the exported model (model.onnx or model.plan)",
    )
    parser.add_argument(
        "--device",
        type=str,
        default=os.environ.get("YOLO26_EXPORT_DEVICE", "0"),
        help="CUDA device index for export (default: 0)",
    )
    parser.add_argument(
        "--tensorrt",
        action="store_true",
        help="Export TensorRT FP16 engine instead of ONNX (requires >4 GB VRAM)",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip post-export validation",
    )
    args = parser.parse_args()

    try:
        if args.tensorrt:
            export_to_tensorrt(args.model_path, args.output_path, device=args.device)
        else:
            export_to_onnx(args.model_path, args.output_path, device=args.device)

        if not args.skip_validation:
            if not validate_model(args.output_path):
                logger.error("Post-export validation failed")
                return 1

        fmt = "TensorRT" if args.tensorrt else "ONNX"
        logger.info(f"YOLO26m {fmt} export complete")
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
