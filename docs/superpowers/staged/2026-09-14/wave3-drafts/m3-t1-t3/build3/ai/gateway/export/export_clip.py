"""Export SigLIP 2 Base Vision Encoder ONNX for Triton Inference Server.

Copies the pre-exported SigLIP 2 vision encoder ONNX model from the model zoo
to the Triton cache directory. No PyTorch export is needed since the ONNX
community provides pre-built models.

Previous version exported CLIP ViT-L/14 (1.2GB) from PyTorch to ONNX to TensorRT.
SigLIP 2 Base is 178MB FP16 ONNX, saving 1,035MB VRAM.

Source:  onnx-community/siglip2-base-patch16-224-ONNX
Input:   pixel_values  (B, 3, 224, 224)  FP32
Output:  pooler_output (B, 768)          FP32

L2 normalization is NOT applied in the model -- the gateway adapter handles
that at serving time.

Usage:
    # Copy FP16 vision model to Triton cache
    python export_clip.py

    # Copy FP32 vision model instead
    python export_clip.py --precision fp32

    # Custom paths
    python export_clip.py \\
        --model-path /models/zoo/siglip2-base-patch16-224 \\
        --output-path /models/cache/clip/1/model.onnx
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import sys
from pathlib import Path

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

MODEL_NAME = "clip"
INPUT_SIZE = (224, 224)
EMBEDDING_DIM = 768

# Map precision to ONNX filename in the model zoo
PRECISION_FILES = {
    "fp16": "vision_model_fp16.onnx",
    "fp32": "vision_model.onnx",
    "int8": "vision_model_int8.onnx",
    "q4": "vision_model_q4.onnx",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Copy SigLIP 2 Base vision encoder ONNX to Triton cache",
    )
    parser.add_argument(
        "--model-path",
        default=os.environ.get("SIGLIP2_MODEL_PATH", "/models/model-zoo/siglip2-base-patch16-224"),
        help="Path to SigLIP 2 ONNX model directory",
    )
    parser.add_argument(
        "--output-path",
        default="/models/cache/clip/1/model.onnx",
        help="Output ONNX model path for Triton",
    )
    parser.add_argument(
        "--precision",
        choices=list(PRECISION_FILES.keys()),
        default="fp16",
        help="Model precision variant (default: fp16)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Copy the SigLIP 2 vision encoder ONNX to Triton cache."""
    args = parse_args(argv)

    logger.info("=" * 70)
    logger.info("SigLIP 2 Base Vision Encoder - Triton Setup")
    logger.info("=" * 70)
    logger.info("  Model path:  %s", args.model_path)
    logger.info("  Output path: %s", args.output_path)
    logger.info("  Precision:   %s", args.precision)
    logger.info("=" * 70)

    onnx_filename = PRECISION_FILES[args.precision]
    source_path = Path(args.model_path) / "onnx" / onnx_filename

    if not source_path.exists():
        logger.error("Source ONNX not found: %s", source_path)
        logger.error(
            "Download with: huggingface-cli download "
            "onnx-community/siglip2-base-patch16-224-ONNX "
            "--local-dir %s",
            args.model_path,
        )
        sys.exit(1)

    output_path = Path(args.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Copying %s -> %s", source_path, output_path)
    shutil.copy2(str(source_path), str(output_path))

    size_mb = output_path.stat().st_size / (1024 * 1024)
    logger.info("Done! Model size: %.1f MB", size_mb)
    logger.info("  Input:  pixel_values (B, 3, 224, 224) FP32")
    logger.info("  Output: pooler_output (B, 768) FP32")


if __name__ == "__main__":
    main()
