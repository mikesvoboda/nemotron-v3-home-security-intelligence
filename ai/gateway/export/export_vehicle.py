#!/usr/bin/env python3
"""Export Vehicle Classifier (ResNet-50) to ONNX format for Triton Inference Server.

Model: ResNet-50 fine-tuned for 11-class vehicle segment classification.
Source: /models/zoo/vehicle-segment-classification (pytorch_model.bin + classes.txt)
Input: (B, 3, 224, 224) FP32 — ImageNet-normalized
Output: (B, 11) FP32 — class logits for vehicle types

Vehicle classes:
    articulated_truck, background, bicycle, bus, car, motorcycle,
    non_motorized_vehicle, pedestrian, pickup_truck, single_unit_truck, work_van

Usage:
    python export_vehicle.py \
        --model-path /models/zoo/vehicle-segment-classification \
        --output-path /models/repository/vehicle/1/model.onnx
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

import numpy as np
import torch
from torchvision import models, transforms

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Default vehicle segment classes (must match training)
DEFAULT_VEHICLE_CLASSES: list[str] = [
    "articulated_truck",
    "background",
    "bicycle",
    "bus",
    "car",
    "motorcycle",
    "non_motorized_vehicle",
    "pedestrian",
    "pickup_truck",
    "single_unit_truck",
    "work_van",
]

# Input dimensions matching the training transform
INPUT_HEIGHT = 224
INPUT_WIDTH = 224

# ImageNet normalization constants
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


def load_pytorch_model(model_path: str) -> tuple[torch.nn.Module, list[str]]:
    """Load the ResNet-50 vehicle classifier from a model directory.

    Args:
        model_path: Path to the model directory containing pytorch_model.bin
                    and optionally classes.txt.

    Returns:
        Tuple of (model, class_names).

    Raises:
        FileNotFoundError: If pytorch_model.bin is not found.
    """
    model_dir = Path(model_path)

    # Load class names
    classes_file = model_dir / "classes.txt"
    if classes_file.exists():
        classes = classes_file.read_text().strip().splitlines()
        logger.info(f"Loaded {len(classes)} classes from classes.txt")
    else:
        classes = DEFAULT_VEHICLE_CLASSES
        logger.info(f"Using default {len(classes)} vehicle classes")

    # Build ResNet-50 architecture with correct output size
    model = models.resnet50(weights=None)
    num_ftrs = model.fc.in_features
    model.fc = torch.nn.Linear(num_ftrs, len(classes))

    # Load trained weights
    weights_file = model_dir / "pytorch_model.bin"
    if not weights_file.exists():
        raise FileNotFoundError(f"Model weights not found: {weights_file}")

    state_dict = torch.load(str(weights_file), map_location="cpu", weights_only=True)
    model.load_state_dict(state_dict)
    model.eval()

    logger.info(f"Loaded VehicleClassifier from {model_path} ({len(classes)} classes)")
    return model, classes


def export_to_onnx(
    model: torch.nn.Module,
    output_path: str,
    num_classes: int,
) -> None:
    """Export the PyTorch model to ONNX format.

    Args:
        model: The loaded PyTorch model in eval mode.
        output_path: Destination path for the ONNX file.
        num_classes: Number of output classes.
    """
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create dummy input with dynamic batch dimension
    dummy_input = torch.randn(1, 3, INPUT_HEIGHT, INPUT_WIDTH, dtype=torch.float32)

    # Define dynamic axes for batch dimension
    dynamic_axes = {
        "input": {0: "batch_size"},
        "output": {0: "batch_size"},
    }

    logger.info(f"Exporting to ONNX: {output_path}")
    logger.info(f"  Input shape: (B, 3, {INPUT_HEIGHT}, {INPUT_WIDTH}) FP32")
    logger.info(f"  Output shape: (B, {num_classes}) FP32")
    logger.info("  Opset version: 21")

    torch.onnx.export(
        model,
        dummy_input,
        output_path,
        export_params=True,
        opset_version=21,
        do_constant_folding=True,
        input_names=["input"],
        output_names=["output"],
        dynamic_axes=dynamic_axes,
    )

    # Report file size
    file_size_mb = Path(output_path).stat().st_size / (1024 * 1024)
    logger.info(f"ONNX model saved: {output_path} ({file_size_mb:.1f} MB)")
    logger.info(
        f"Estimated VRAM at runtime: ~{file_size_mb * 1.1:.0f} MB (model weights + buffers)"
    )


def validate_onnx(
    pytorch_model: torch.nn.Module,
    onnx_path: str,
    _num_classes: int,
) -> bool:
    """Validate the ONNX model by comparing outputs against PyTorch.

    Runs inference with random inputs on both PyTorch and ONNX Runtime,
    then checks that outputs are numerically close.

    Args:
        pytorch_model: The original PyTorch model.
        onnx_path: Path to the exported ONNX file.
        num_classes: Number of output classes.

    Returns:
        True if validation passes, False otherwise.
    """
    try:
        import onnx
        import onnxruntime as ort
    except ImportError:
        logger.warning("onnx or onnxruntime not installed — skipping validation")
        return True

    logger.info("Validating ONNX model against PyTorch...")

    # Check ONNX model structure
    onnx_model = onnx.load(onnx_path)
    onnx.checker.check_model(onnx_model)
    logger.info("ONNX model structure check passed")

    # Create ONNX Runtime session
    providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    session = ort.InferenceSession(onnx_path, providers=providers)

    # Test with multiple batch sizes to validate dynamic axes
    test_batch_sizes = [1, 2, 4]
    all_passed = True
    # ResNet-50 with ONNX constant-folding can produce differences up to ~1e-3
    tolerance = 1e-3

    for batch_size in test_batch_sizes:
        test_input = np.random.randn(batch_size, 3, INPUT_HEIGHT, INPUT_WIDTH).astype(np.float32)

        # PyTorch inference
        with torch.inference_mode():
            pt_input = torch.from_numpy(test_input)
            pt_output = pytorch_model(pt_input).numpy()

        # ONNX Runtime inference
        ort_output = session.run(None, {"input": test_input})[0]

        # Compare outputs
        max_diff = np.abs(pt_output - ort_output).max()
        mean_diff = np.abs(pt_output - ort_output).mean()

        if max_diff < tolerance:
            logger.info(
                f"  Batch size {batch_size}: PASS "
                f"(max_diff={max_diff:.2e}, mean_diff={mean_diff:.2e})"
            )
        else:
            logger.error(
                f"  Batch size {batch_size}: FAIL "
                f"(max_diff={max_diff:.2e}, mean_diff={mean_diff:.2e}, tol={tolerance:.0e})"
            )
            all_passed = False

    if all_passed:
        logger.info("ONNX validation PASSED for all batch sizes")
    else:
        logger.error("ONNX validation FAILED — outputs diverge from PyTorch")

    return all_passed


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Vehicle Classifier (ResNet-50) to ONNX")
    parser.add_argument(
        "--model-path",
        type=str,
        default="/models/zoo/vehicle-segment-classification",
        help="Path to the vehicle model directory (contains pytorch_model.bin)",
    )
    parser.add_argument(
        "--output-path",
        type=str,
        default="vehicle/1/model.onnx",
        help="Output path for the ONNX model file",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip ONNX validation step",
    )
    args = parser.parse_args()

    try:
        # Load PyTorch model
        model, classes = load_pytorch_model(args.model_path)

        # Export to ONNX
        export_to_onnx(model, args.output_path, num_classes=len(classes))

        # Validate
        if not args.skip_validation:
            if not validate_onnx(model, args.output_path, num_classes=len(classes)):
                logger.error("Validation failed — exported ONNX may produce incorrect results")
                return 1

        logger.info("Vehicle classifier export complete")
        return 0

    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        return 1
    except Exception as e:
        logger.error(f"Export failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
