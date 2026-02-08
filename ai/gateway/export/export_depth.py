#!/usr/bin/env python3
"""Export Depth Anything V2 Small to ONNX format for Triton Inference Server.

Model: Depth Anything V2 Small (AutoModelForDepthEstimation)
Source: /models/zoo/depth-anything-v2-small
Input: (B, 3, 518, 518) FP32 — processor-normalized (Depth Anything V2 uses 518x518)
Output: (B, 1, H, W) FP32 — predicted depth map

The Depth Anything V2 Small model uses an input resolution of 518x518 as defined
by its AutoImageProcessor configuration. The output depth map has the same spatial
dimensions as the input.

Usage:
    python export_depth.py \
        --model-path /models/zoo/depth-anything-v2-small \
        --output-path /models/repository/depth/1/model.onnx
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

# Depth Anything V2 Small default input size from AutoImageProcessor config.
# The processor resizes inputs to this resolution before feeding the model.
DEFAULT_INPUT_HEIGHT = 518
DEFAULT_INPUT_WIDTH = 518


def load_pytorch_model(model_path: str) -> tuple[torch.nn.Module, int, int]:
    """Load the Depth Anything V2 Small model and determine input size.

    Reads the AutoImageProcessor config to find the actual input resolution,
    falling back to 518x518 if unavailable.

    Args:
        model_path: Path to the model directory (HuggingFace format).

    Returns:
        Tuple of (model, input_height, input_width).
    """
    from transformers import AutoImageProcessor, AutoModelForDepthEstimation

    model_dir = Path(model_path)
    if model_dir.exists():
        local_path = str(model_dir.resolve())
        logger.info(f"Loading DepthEstimator from local path: {local_path}")
    else:
        local_path = model_path
        logger.info(f"Loading DepthEstimator from: {local_path}")

    # Load processor to discover expected input size
    processor = AutoImageProcessor.from_pretrained(local_path)

    input_height = DEFAULT_INPUT_HEIGHT
    input_width = DEFAULT_INPUT_WIDTH

    # Try to extract size from processor config
    if hasattr(processor, "size"):
        size_config = processor.size
        if isinstance(size_config, dict):
            input_height = size_config.get("height", DEFAULT_INPUT_HEIGHT)
            input_width = size_config.get("width", DEFAULT_INPUT_WIDTH)
        elif isinstance(size_config, int):
            input_height = size_config
            input_width = size_config

    logger.info(f"Processor input size: {input_height}x{input_width}")

    # Load model
    model = AutoModelForDepthEstimation.from_pretrained(local_path)
    model.eval()

    logger.info("DepthEstimator loaded successfully")
    return model, input_height, input_width


def export_to_onnx(
    model: torch.nn.Module,
    output_path: str,
    input_height: int,
    input_width: int,
) -> None:
    """Export the depth estimation model to ONNX format.

    Wraps the HuggingFace model to accept a plain tensor and output the
    predicted_depth tensor directly.

    Args:
        model: Loaded HuggingFace AutoModelForDepthEstimation.
        output_path: Destination path for the ONNX file.
        input_height: Input image height.
        input_width: Input image width.
    """
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    class DepthWrapper(torch.nn.Module):
        """Wraps AutoModelForDepthEstimation to return predicted_depth tensor."""

        def __init__(self, hf_model: torch.nn.Module):
            super().__init__()
            self.model = hf_model

        def forward(self, pixel_values: torch.Tensor) -> torch.Tensor:
            outputs = self.model(pixel_values=pixel_values)
            return outputs.predicted_depth

    wrapper = DepthWrapper(model)
    wrapper.eval()

    dummy_input = torch.randn(1, 3, input_height, input_width, dtype=torch.float32)

    # Run a test forward pass to determine output shape
    with torch.inference_mode():
        test_output = wrapper(dummy_input)
    output_shape = list(test_output.shape)
    logger.info(f"Test forward pass output shape: {output_shape}")

    dynamic_axes = {
        "input": {0: "batch_size"},
        "depth_map": {0: "batch_size"},
    }

    logger.info(f"Exporting to ONNX: {output_path}")
    logger.info(f"  Input shape: (B, 3, {input_height}, {input_width}) FP32")
    logger.info(f"  Output shape: (B, {', '.join(str(s) for s in output_shape[1:])}) FP32")
    logger.info("  Opset version: 17")

    torch.onnx.export(
        wrapper,
        dummy_input,
        output_path,
        export_params=True,
        opset_version=17,
        do_constant_folding=True,
        input_names=["input"],
        output_names=["depth_map"],
        dynamic_axes=dynamic_axes,
    )

    file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    logger.info(f"ONNX model saved: {output_path} ({file_size_mb:.1f} MB)")
    logger.info(f"Estimated VRAM at runtime: ~{file_size_mb * 1.1:.0f} MB (model weights + buffers)")


def validate_onnx(
    pytorch_model: torch.nn.Module,
    onnx_path: str,
    input_height: int,
    input_width: int,
) -> bool:
    """Validate the ONNX model by comparing outputs against PyTorch.

    Args:
        pytorch_model: The original HuggingFace model.
        onnx_path: Path to the exported ONNX file.
        input_height: Input image height.
        input_width: Input image width.

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

    test_batch_sizes = [1, 2]
    all_passed = True

    for batch_size in test_batch_sizes:
        test_input = np.random.randn(batch_size, 3, input_height, input_width).astype(np.float32)

        # PyTorch inference
        with torch.inference_mode():
            pt_input = torch.from_numpy(test_input)
            pt_output = pytorch_model(pixel_values=pt_input).predicted_depth.numpy()

        # ONNX Runtime inference
        ort_output = session.run(None, {"input": test_input})[0]

        max_diff = np.abs(pt_output - ort_output).max()
        mean_diff = np.abs(pt_output - ort_output).mean()

        # Depth models can have slightly larger numerical differences
        tolerance = 1e-3
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
    parser = argparse.ArgumentParser(
        description="Export Depth Anything V2 Small to ONNX"
    )
    parser.add_argument(
        "--model-path",
        type=str,
        default="/models/zoo/depth-anything-v2-small",
        help="Path to the Depth Anything V2 model directory (HuggingFace format)",
    )
    parser.add_argument(
        "--output-path",
        type=str,
        default="depth/1/model.onnx",
        help="Output path for the ONNX model file",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip ONNX validation step",
    )
    args = parser.parse_args()

    try:
        model, input_height, input_width = load_pytorch_model(args.model_path)
        export_to_onnx(model, args.output_path, input_height, input_width)

        if not args.skip_validation:
            if not validate_onnx(model, args.output_path, input_height, input_width):
                logger.error("Validation failed — exported ONNX may produce incorrect results")
                return 1

        logger.info("Depth estimator export complete")
        return 0

    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        return 1
    except Exception as e:
        logger.error(f"Export failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
