#!/usr/bin/env python3
"""Export Demographics (Age + Gender) ViT classifiers to ONNX for Triton Inference Server.

Models:
  - Age: ViTForImageClassification from /models/zoo/vit-age-classifier
  - Gender: ViTForImageClassification from /models/zoo/vit-gender-classifier

Both use HuggingFace AutoImageProcessor / ViTForImageClassification.
Input: (B, 3, 224, 224) FP32 — processor-normalized
Output: (B, num_classes) FP32 — class logits

Age classes (nateraw/vit-age-classifier style):
    0-2, 3-9, 10-19, 20-29, 30-39, 40-49, 50-59, 60-69, more than 70

Gender classes:
    female, male

Usage:
    python export_demographics.py \
        --age-model-path /models/zoo/vit-age-classifier \
        --gender-model-path /models/zoo/vit-gender-classifier \
        --age-output-path /models/repository/demographics_age/1/model.onnx \
        --gender-output-path /models/repository/demographics_gender/1/model.onnx
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

# ViT-based classifiers use 224x224 input by default
INPUT_HEIGHT = 224
INPUT_WIDTH = 224


def load_vit_model(
    model_path: str, model_name: str
) -> tuple[torch.nn.Module, int]:
    """Load a ViT image classification model from a HuggingFace directory.

    Args:
        model_path: Path to model directory or HuggingFace model ID.
        model_name: Human-readable name for logging (e.g., "age", "gender").

    Returns:
        Tuple of (model, num_classes).

    Raises:
        FileNotFoundError: If local model path does not exist.
    """
    from transformers import ViTForImageClassification

    model_dir = Path(model_path)
    if model_dir.exists():
        local_path = str(model_dir.resolve())
        logger.info(f"Loading {model_name} model from local path: {local_path}")
    else:
        local_path = model_path
        logger.info(f"Loading {model_name} model from: {local_path}")

    model = ViTForImageClassification.from_pretrained(local_path)
    model.eval()

    num_classes = model.config.num_labels
    labels = []
    if hasattr(model.config, "id2label") and model.config.id2label:
        labels = [
            model.config.id2label.get(str(i), f"{model_name}_{i}")
            for i in range(num_classes)
        ]
    logger.info(f"{model_name.capitalize()} model: {num_classes} classes — {labels}")

    return model, num_classes


def export_vit_to_onnx(
    model: torch.nn.Module,
    output_path: str,
    model_name: str,
    num_classes: int,
) -> None:
    """Export a ViT classification model to ONNX.

    The ViTForImageClassification model accepts pixel_values as input.
    We wrap it to accept a plain tensor for simpler Triton integration.

    Args:
        model: Loaded HuggingFace ViTForImageClassification model.
        output_path: Destination path for the ONNX file.
        model_name: Human-readable name for logging.
        num_classes: Number of output classes.
    """
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    class VitWrapper(torch.nn.Module):
        """Wraps ViTForImageClassification to accept a plain tensor input.

        This avoids exporting the HuggingFace dict-based interface,
        producing a cleaner ONNX graph with a single tensor input/output.
        """

        def __init__(self, vit_model: torch.nn.Module):
            super().__init__()
            self.vit = vit_model

        def forward(self, pixel_values: torch.Tensor) -> torch.Tensor:
            outputs = self.vit(pixel_values=pixel_values)
            return outputs.logits

    wrapper = VitWrapper(model)
    wrapper.eval()

    dummy_input = torch.randn(1, 3, INPUT_HEIGHT, INPUT_WIDTH, dtype=torch.float32)

    dynamic_axes = {
        "input": {0: "batch_size"},
        "output": {0: "batch_size"},
    }

    logger.info(f"Exporting {model_name} model to ONNX: {output_path}")
    logger.info(f"  Input shape: (B, 3, {INPUT_HEIGHT}, {INPUT_WIDTH}) FP32")
    logger.info(f"  Output shape: (B, {num_classes}) FP32")
    logger.info("  Opset version: 17")

    torch.onnx.export(
        wrapper,
        dummy_input,
        output_path,
        export_params=True,
        opset_version=17,
        do_constant_folding=True,
        input_names=["input"],
        output_names=["output"],
        dynamic_axes=dynamic_axes,
    )

    file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    logger.info(f"ONNX model saved: {output_path} ({file_size_mb:.1f} MB)")
    logger.info(f"Estimated VRAM at runtime: ~{file_size_mb * 1.1:.0f} MB (model weights + buffers)")


def validate_onnx(
    pytorch_model: torch.nn.Module,
    onnx_path: str,
    model_name: str,
    num_classes: int,
) -> bool:
    """Validate ONNX model by comparing outputs against PyTorch.

    Args:
        pytorch_model: The original HuggingFace ViT model.
        onnx_path: Path to the exported ONNX file.
        model_name: Human-readable name for logging.
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

    logger.info(f"Validating {model_name} ONNX model against PyTorch...")

    onnx_model = onnx.load(onnx_path)
    onnx.checker.check_model(onnx_model)
    logger.info(f"  {model_name} ONNX structure check passed")

    providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    session = ort.InferenceSession(onnx_path, providers=providers)

    test_batch_sizes = [1, 2, 4]
    all_passed = True

    for batch_size in test_batch_sizes:
        test_input = np.random.randn(batch_size, 3, INPUT_HEIGHT, INPUT_WIDTH).astype(np.float32)

        # PyTorch inference (ViTForImageClassification expects pixel_values)
        with torch.inference_mode():
            pt_input = torch.from_numpy(test_input)
            pt_output = pytorch_model(pixel_values=pt_input).logits.numpy()

        # ONNX Runtime inference
        ort_output = session.run(None, {"input": test_input})[0]

        max_diff = np.abs(pt_output - ort_output).max()
        mean_diff = np.abs(pt_output - ort_output).mean()

        if max_diff < 1e-4:
            logger.info(
                f"  {model_name} batch {batch_size}: PASS "
                f"(max_diff={max_diff:.2e}, mean_diff={mean_diff:.2e})"
            )
        else:
            logger.error(
                f"  {model_name} batch {batch_size}: FAIL "
                f"(max_diff={max_diff:.2e}, mean_diff={mean_diff:.2e})"
            )
            all_passed = False

    if all_passed:
        logger.info(f"{model_name.capitalize()} ONNX validation PASSED")
    else:
        logger.error(f"{model_name.capitalize()} ONNX validation FAILED")

    return all_passed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export Demographics (Age + Gender) ViT classifiers to ONNX"
    )
    parser.add_argument(
        "--age-model-path",
        type=str,
        default="/models/zoo/vit-age-classifier",
        help="Path to the age classifier model directory",
    )
    parser.add_argument(
        "--gender-model-path",
        type=str,
        default="/models/zoo/vit-gender-classifier",
        help="Path to the gender classifier model directory",
    )
    parser.add_argument(
        "--age-output-path",
        type=str,
        default="demographics_age/1/model.onnx",
        help="Output path for the age ONNX model",
    )
    parser.add_argument(
        "--gender-output-path",
        type=str,
        default="demographics_gender/1/model.onnx",
        help="Output path for the gender ONNX model",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip ONNX validation step",
    )
    parser.add_argument(
        "--age-only",
        action="store_true",
        help="Export only the age model (skip gender)",
    )
    args = parser.parse_args()

    success = True

    # --- Age Model ---
    try:
        logger.info("=" * 60)
        logger.info("Exporting AGE classifier")
        logger.info("=" * 60)

        age_model, age_num_classes = load_vit_model(args.age_model_path, "age")
        export_vit_to_onnx(age_model, args.age_output_path, "age", age_num_classes)

        if not args.skip_validation:
            if not validate_onnx(age_model, args.age_output_path, "age", age_num_classes):
                logger.error("Age model validation failed")
                success = False

        logger.info("Age classifier export complete")

    except FileNotFoundError as e:
        logger.error(f"Age model not found: {e}")
        success = False
    except Exception as e:
        logger.error(f"Age model export failed: {e}", exc_info=True)
        success = False

    # --- Gender Model ---
    if not args.age_only:
        try:
            logger.info("")
            logger.info("=" * 60)
            logger.info("Exporting GENDER classifier")
            logger.info("=" * 60)

            gender_model, gender_num_classes = load_vit_model(
                args.gender_model_path, "gender"
            )
            export_vit_to_onnx(
                gender_model, args.gender_output_path, "gender", gender_num_classes
            )

            if not args.skip_validation:
                if not validate_onnx(
                    gender_model,
                    args.gender_output_path,
                    "gender",
                    gender_num_classes,
                ):
                    logger.error("Gender model validation failed")
                    success = False

            logger.info("Gender classifier export complete")

        except FileNotFoundError as e:
            logger.error(f"Gender model not found: {e}")
            success = False
        except Exception as e:
            logger.error(f"Gender model export failed: {e}", exc_info=True)
            success = False
    else:
        logger.info("Skipping gender model export (--age-only)")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
