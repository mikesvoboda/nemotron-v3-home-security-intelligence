#!/usr/bin/env python3
"""Export YOLO26m to ONNX for Triton Inference Server.

Model: Ultralytics YOLO26m (80 COCO object detection classes)
Source: /models/zoo/yolo26/yolo26m.pt
Input: (1, 3, 640, 640) FP32 -- letterboxed and normalized
Output: (1, 84, 8400) FP32 -- raw YOLO detections (4 box + 80 class scores)

The Ultralytics export pipeline handles the full conversion:
  .pt -> ONNX                                      [default / --onnx-only]
  .pt -> ONNX -> INT8 quantized ONNX               [--int8]
  .pt -> ONNX -> TensorRT FP16 engine (.engine)    [--tensorrt]

INT8 quantization (NEM-5547) uses ONNX Runtime's quantization APIs to produce
a smaller, faster model that runs on the existing onnxruntime Triton backend.
Dynamic quantization requires no calibration data; static quantization uses
representative frames from security cameras for optimal accuracy.

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

    # INT8 quantized ONNX (dynamic — no calibration data needed)
    python export_yolo26.py \\
        --model-path /models/zoo/yolo26/yolo26m.pt \\
        --output-path /models/cache/yolo26/1/model.onnx \\
        --int8

    # INT8 quantized ONNX (static — uses calibration data for better accuracy)
    python export_yolo26.py \\
        --model-path /models/zoo/yolo26/yolo26m.pt \\
        --output-path /models/cache/yolo26/1/model.onnx \\
        --int8 --calibration-data /export/foscam/

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
from typing import Any

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


def quantize_onnx_int8(
    onnx_path: str,
    output_path: str,
    calibration_data_dir: str | None = None,
) -> None:
    """Quantize an ONNX model to INT8 using ONNX Runtime quantization.

    Supports two modes:
    - Dynamic quantization (no calibration data): quantizes weights statically,
      activations dynamically at runtime. Fast to produce, no data needed.
    - Static quantization (with calibration data): quantizes both weights and
      activations using representative data for optimal accuracy.

    Args:
        onnx_path: Path to the FP32 ONNX model to quantize.
        output_path: Destination path for the INT8 ONNX model.
        calibration_data_dir: Optional directory containing calibration images.
            If provided, uses static quantization for better accuracy.
            If None, uses dynamic quantization (no data needed).

    Raises:
        ImportError: If onnxruntime.quantization is not available.
        RuntimeError: If quantization fails.
    """
    try:
        from onnxruntime.quantization import QuantType, quantize_dynamic
    except ImportError as e:
        raise ImportError(
            "onnxruntime quantization not available. "
            "Install with: pip install onnxruntime onnxruntime-gpu"
        ) from e

    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    if calibration_data_dir and Path(calibration_data_dir).is_dir():
        # Static quantization with calibration data
        logger.info("Using static INT8 quantization with calibration data")
        logger.info(f"Calibration data: {calibration_data_dir}")

        try:
            from onnxruntime.quantization import CalibrationDataReader, quantize_static

            class YOLOCalibrationReader(CalibrationDataReader):
                """Reads calibration images for static INT8 quantization."""

                def __init__(self, data_dir: str, input_name: str = "images") -> None:
                    import numpy as np
                    from PIL import Image as PILImage

                    self.input_name = input_name
                    data_path = Path(data_dir)
                    self.image_paths = sorted(
                        [str(p) for p in data_path.rglob("*.jpg")]
                        + [str(p) for p in data_path.rglob("*.jpeg")]
                        + [str(p) for p in data_path.rglob("*.png")]
                    )[:500]  # Cap at 500 images
                    self.index = 0
                    self._pil = PILImage
                    self._np = np
                    logger.info(f"Found {len(self.image_paths)} calibration images")

                def get_next(self) -> dict[str, Any] | None:
                    if self.index >= len(self.image_paths):
                        return None
                    img_path = self.image_paths[self.index]
                    self.index += 1
                    try:
                        img = self._pil.open(img_path).convert("RGB").resize((IMGSZ, IMGSZ))
                        arr = self._np.array(img, dtype=self._np.float32) / 255.0
                        arr = arr.transpose(2, 0, 1)  # HWC -> CHW
                        arr = self._np.expand_dims(arr, axis=0)  # Add batch dim
                        return {self.input_name: arr}
                    except Exception as e:
                        logger.debug(f"Skipping calibration image {img_path}: {e}")
                        return self.get_next()

            calibration_reader = YOLOCalibrationReader(calibration_data_dir)
            if not calibration_reader.image_paths:
                logger.warning("No calibration images found, falling back to dynamic quantization")
                quantize_dynamic(
                    onnx_path,
                    output_path,
                    weight_type=QuantType.QInt8,
                )
            else:
                quantize_static(
                    onnx_path,
                    output_path,
                    calibration_reader,
                    quant_format=None,  # Use default QDQ format
                    weight_type=QuantType.QInt8,
                    activation_type=QuantType.QUInt8,
                )
        except ImportError:
            logger.warning("Static quantization not available, falling back to dynamic")
            quantize_dynamic(
                onnx_path,
                output_path,
                weight_type=QuantType.QInt8,
            )
    else:
        # Dynamic quantization (no calibration data needed)
        logger.info("Using dynamic INT8 quantization (no calibration data)")
        quantize_dynamic(
            onnx_path,
            output_path,
            weight_type=QuantType.QInt8,
        )

    file_size_mb = Path(output_path).stat().st_size / (1024 * 1024)
    orig_size_mb = Path(onnx_path).stat().st_size / (1024 * 1024)
    reduction = (1 - file_size_mb / orig_size_mb) * 100 if orig_size_mb > 0 else 0
    logger.info(
        f"INT8 quantized model saved: {output_path} "
        f"({file_size_mb:.1f} MB, {reduction:.0f}% smaller than FP32)"
    )


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
        "--int8",
        action="store_true",
        help="Apply INT8 quantization to ONNX model (NEM-5547: ~20-40%% faster, ~50%% smaller)",
    )
    parser.add_argument(
        "--calibration-data",
        type=str,
        default=None,
        help="Directory containing calibration images for static INT8 quantization. "
        "If omitted, uses dynamic quantization (no data needed, slightly less accurate).",
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
        elif args.int8:
            # INT8 quantization: export FP32 ONNX first, then quantize
            # Use a temporary path for the intermediate FP32 ONNX
            fp32_path = args.output_path + ".fp32.onnx"
            export_to_onnx(args.model_path, fp32_path, device=args.device)
            quantize_onnx_int8(
                fp32_path,
                args.output_path,
                calibration_data_dir=args.calibration_data,
            )
            # Clean up intermediate FP32 ONNX
            Path(fp32_path).unlink(missing_ok=True)
            logger.info("Removed intermediate FP32 ONNX")
        else:
            export_to_onnx(args.model_path, args.output_path, device=args.device)

        if not args.skip_validation:
            if not validate_model(args.output_path):
                logger.error("Post-export validation failed")
                return 1

        fmt = "TensorRT" if args.tensorrt else ("ONNX INT8" if args.int8 else "ONNX")
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
