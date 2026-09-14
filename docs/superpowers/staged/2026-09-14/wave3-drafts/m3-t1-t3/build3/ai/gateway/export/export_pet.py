#!/usr/bin/env python3
"""Export Pet Classifier (ResNet-18) to ONNX format for Triton Inference Server.

Model: HuggingFace AutoModelForImageClassification (ResNet-18 fine-tuned for cat/dog).
Source: /models/zoo/pet-classifier
Input: (B, 3, 224, 224) FP32 — AutoImageProcessor-normalized
Output: (B, 2) FP32 — class logits [cat, dog]

The pet classifier uses HuggingFace's AutoImageProcessor for preprocessing,
which handles resize and normalization. The ONNX export wraps the model to
accept a raw pixel_values tensor.

Usage:
    python export_pet.py \
        --model-path /models/zoo/pet-classifier \
        --output-path /models/repository/pet/1/model.onnx
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

import numpy as np
import torch

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Standard input size for ResNet-18 pet classifier
INPUT_HEIGHT = 224
INPUT_WIDTH = 224

# Default labels
PET_LABELS = ["cat", "dog"]


def load_pytorch_model(model_path: str) -> tuple[torch.nn.Module, int, list[str]]:
    """Load the HuggingFace pet classifier model.

    Args:
        model_path: Path to the model directory (HuggingFace format).

    Returns:
        Tuple of (model, num_classes, class_labels).
    """
    from transformers import AutoModelForImageClassification

    model_dir = Path(model_path)
    if model_dir.exists():
        local_path = str(model_dir.resolve())
        logger.info(f"Loading PetClassifier from local path: {local_path}")
    else:
        local_path = model_path
        logger.info(f"Loading PetClassifier from: {local_path}")

    model = AutoModelForImageClassification.from_pretrained(
        local_path, local_files_only=model_dir.exists()
    )
    model.eval()

    num_classes = model.config.num_labels

    # Extract labels from model config
    labels = PET_LABELS[:num_classes]
    if hasattr(model.config, "id2label") and model.config.id2label:
        labels = [
            model.config.id2label.get(
                str(i), PET_LABELS[i] if i < len(PET_LABELS) else f"class_{i}"
            )
            for i in range(num_classes)
        ]

    logger.info(f"PetClassifier loaded: {num_classes} classes — {labels}")
    return model, num_classes, labels


def export_to_onnx(
    model: torch.nn.Module,
    output_path: str,
    num_classes: int,
) -> None:
    """Export the pet classifier to ONNX format.

    Wraps the HuggingFace model to accept a plain pixel_values tensor,
    producing a clean ONNX graph for Triton.

    Args:
        model: Loaded HuggingFace AutoModelForImageClassification.
        output_path: Destination path for the ONNX file.
        num_classes: Number of output classes.
    """
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    class PetWrapper(torch.nn.Module):
        """Wraps AutoModelForImageClassification to accept a plain tensor."""

        def __init__(self, hf_model: torch.nn.Module):
            super().__init__()
            self.model = hf_model

        def forward(self, pixel_values: torch.Tensor) -> torch.Tensor:
            outputs = self.model(pixel_values=pixel_values)
            return outputs.logits

    wrapper = PetWrapper(model)
    wrapper.eval()

    dummy_input = torch.randn(1, 3, INPUT_HEIGHT, INPUT_WIDTH, dtype=torch.float32)

    dynamic_axes = {
        "input": {0: "batch_size"},
        "output": {0: "batch_size"},
    }

    logger.info(f"Exporting to ONNX: {output_path}")
    logger.info(f"  Input shape: (B, 3, {INPUT_HEIGHT}, {INPUT_WIDTH}) FP32")
    logger.info(f"  Output shape: (B, {num_classes}) FP32")
    logger.info("  Opset version: 17")

    torch.onnx.export(
        wrapper,
        dummy_input,
        output_path,
        export_params=True,
        opset_version=21,
        do_constant_folding=True,
        input_names=["input"],
        output_names=["output"],
        dynamic_axes=dynamic_axes,
    )

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

    Args:
        pytorch_model: The original HuggingFace model.
        onnx_path: Path to the exported ONNX file.
        num_classes: Number of output classes.

    Returns:
        True if validation passes.
    """
    try:
        import onnx
        import onnxruntime as ort
    except ImportError:
        logger.warning("onnx or onnxruntime not installed — skipping validation")
        return True

    logger.info("Validating ONNX model against PyTorch...")

    onnx_model = onnx.load(onnx_path)
    onnx.checker.check_model(onnx_model)
    logger.info("ONNX model structure check passed")

    providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    session = ort.InferenceSession(onnx_path, providers=providers)

    test_batch_sizes = [1, 2, 4]
    all_passed = True

    for batch_size in test_batch_sizes:
        test_input = np.random.randn(batch_size, 3, INPUT_HEIGHT, INPUT_WIDTH).astype(np.float32)

        # PyTorch inference
        with torch.inference_mode():
            pt_input = torch.from_numpy(test_input)
            pt_output = pytorch_model(pixel_values=pt_input).logits.numpy()

        # ONNX Runtime inference
        ort_output = session.run(None, {"input": test_input})[0]

        max_diff = np.abs(pt_output - ort_output).max()
        mean_diff = np.abs(pt_output - ort_output).mean()

        if max_diff < 1e-3:
            logger.info(
                f"  Batch size {batch_size}: PASS "
                f"(max_diff={max_diff:.2e}, mean_diff={mean_diff:.2e})"
            )
        else:
            logger.error(
                f"  Batch size {batch_size}: FAIL "
                f"(max_diff={max_diff:.2e}, mean_diff={mean_diff:.2e})"
            )
            all_passed = False

    if all_passed:
        logger.info("ONNX validation PASSED for all batch sizes")
    else:
        logger.error("ONNX validation FAILED — outputs diverge from PyTorch")

    return all_passed


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Pet Classifier (ResNet-18) to ONNX")
    parser.add_argument(
        "--model-path",
        type=str,
        default="/models/zoo/pet-classifier",
        help="Path to the pet classifier model directory (HuggingFace format)",
    )
    parser.add_argument(
        "--output-path",
        type=str,
        default="pet/1/model.onnx",
        help="Output path for the ONNX model file",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip ONNX validation step",
    )
    args = parser.parse_args()

    try:
        model, num_classes, labels = load_pytorch_model(args.model_path)
        export_to_onnx(model, args.output_path, num_classes)

        if not args.skip_validation:
            if not validate_onnx(model, args.output_path, num_classes):
                logger.error("Validation failed — exported ONNX may produce incorrect results")
                return 1

        logger.info("Pet classifier export complete")
        return 0

    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        return 1
    except Exception as e:
        logger.error(f"Export failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
