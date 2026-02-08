#!/usr/bin/env python3
"""Export YOLOv8n threat detection model to TensorRT FP16 engine for Triton.

Model: YOLOv8n fine-tuned for weapon/threat detection
Source: /models/zoo/threat-detection-yolov8n/weights/best.pt
Input: (1, 3, 640, 640) FP16 — letterboxed and normalized
Output: Bounding boxes + class IDs + confidence scores per detection

Threat classes: knife, gun, rifle, pistol, bat, crowbar (model-dependent)

The Ultralytics export pipeline handles the full conversion:
  .pt -> ONNX -> TensorRT FP16 engine (.engine)

Since model zoo volumes are mounted read-only, the .pt file is copied to
a temporary writable directory before export.  The resulting .engine file
is then placed at the Triton model repository path.

Environment Variables:
    THREAT_TENSORRT_DEVICE: CUDA device index for export (default: "0")

Usage:
    python export_yolo_threat.py \\
        --model-path /models/zoo/threat-detection-yolov8n/weights/best.pt \\
        --output-path /models/cache/threat/1/model.plan
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
DEFAULT_MODEL_PATH = "/models/zoo/threat-detection-yolov8n/weights/best.pt"
DEFAULT_OUTPUT_PATH = "/models/cache/threat/1/model.plan"

# Export settings
IMGSZ = 640


def export_to_tensorrt(
    model_path: str,
    output_path: str,
    device: str = "0",
) -> None:
    """Export YOLOv8n threat detector to TensorRT FP16 engine via Ultralytics.

    The export process:
    1. Copies the .pt model to a writable temp directory (zoo is read-only)
    2. Loads the model via Ultralytics YOLO
    3. Calls model.export(format='engine', half=True) which runs:
       .pt -> ONNX -> TensorRT builder -> serialized .engine
    4. Copies the resulting .engine file to the output path

    Args:
        model_path: Path to the YOLOv8n threat detection .pt weights file.
        output_path: Destination path for the TensorRT engine (model.plan).
        device: CUDA device index for export (e.g. "0").

    Raises:
        FileNotFoundError: If the source .pt model does not exist.
        RuntimeError: If TensorRT export fails.
    """
    from ultralytics import YOLO

    model_path_obj = Path(model_path)
    if not model_path_obj.exists():
        raise FileNotFoundError(f"Threat model not found: {model_path}")

    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Source model: {model_path}")
    logger.info(f"Output path: {output_path}")
    logger.info(f"Device: cuda:{device}")
    logger.info("Precision: FP16")
    logger.info(f"Image size: {IMGSZ}")

    # Work in a writable temp directory since model zoo may be read-only
    with tempfile.TemporaryDirectory(prefix="threat_export_") as tmpdir:
        # For the threat model, we need to copy the entire weights directory
        # because Ultralytics may look for adjacent config files (data.yaml, etc.)
        tmp_weights_dir = Path(tmpdir) / "weights"
        tmp_weights_dir.mkdir(parents=True, exist_ok=True)

        # Copy the .pt file
        tmp_model = tmp_weights_dir / model_path_obj.name
        logger.info(f"Copying model to writable directory: {tmp_model}")
        shutil.copy2(model_path, tmp_model)

        # Also copy any sibling config files (data.yaml, args.yaml, etc.)
        src_dir = model_path_obj.parent
        for config_file in src_dir.glob("*.yaml"):
            shutil.copy2(config_file, tmp_weights_dir / config_file.name)
        # Check parent directory too for data.yaml
        parent_dir = src_dir.parent
        for config_file in parent_dir.glob("*.yaml"):
            shutil.copy2(config_file, Path(tmpdir) / config_file.name)

        # Load model from writable copy
        model = YOLO(str(tmp_model))

        # Log detected classes
        if hasattr(model, "names") and model.names:
            logger.info(f"Threat classes: {model.names}")

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

    file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
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

    # 4. Also check parent temp directory
    for engine_file in tmp_model.parent.parent.rglob("*.engine"):
        return engine_file

    return None


def validate_engine(output_path: str) -> bool:
    """Quick validation that the engine file looks reasonable.

    Checks file size and existence.  Full inference validation
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
        description="Export YOLOv8n threat detection to TensorRT FP16 engine for Triton"
    )
    parser.add_argument(
        "--model-path",
        type=str,
        default=DEFAULT_MODEL_PATH,
        help="Path to the threat detection .pt weights file",
    )
    parser.add_argument(
        "--output-path",
        type=str,
        default=DEFAULT_OUTPUT_PATH,
        help="Output path for the TensorRT engine (model.plan)",
    )
    parser.add_argument(
        "--device",
        type=str,
        default=os.environ.get("THREAT_TENSORRT_DEVICE", "0"),
        help="CUDA device index for export (default: 0)",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip post-export validation",
    )
    args = parser.parse_args()

    try:
        export_to_tensorrt(args.model_path, args.output_path, device=args.device)

        if not args.skip_validation:
            if not validate_engine(args.output_path):
                logger.error("Post-export validation failed")
                return 1

        logger.info("YOLOv8n threat detection TensorRT export complete")
        return 0

    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        return 1
    except ImportError as e:
        logger.error(f"Missing dependency: {e}. Ensure ultralytics and tensorrt are installed.")
        return 1
    except Exception as e:
        logger.error(f"Export failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
