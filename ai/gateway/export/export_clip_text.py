#!/usr/bin/env python3
"""Export CLIP text encoder to ONNX for Triton deployment.

Extracts the text encoder (text_model + text_projection) from the full
CLIP model and exports it as an ONNX model suitable for Triton Inference
Server with the ONNX Runtime backend.

Input:  input_ids      (B, 77)  INT64
        attention_mask  (B, 77)  INT64
Output: text_embeds    (B, 768) FP32

L2 normalization is NOT applied in the model -- the gateway adapter
handles that at serving time, matching the vision encoder pattern.

Usage:
    python export_clip_text.py \\
        --model-path /models/zoo/clip-vit-l \\
        --output-path /models/cache/clip_text/1/model.onnx
"""

from __future__ import annotations

import argparse
import logging
import os
import time
from pathlib import Path

import numpy as np
import torch

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

MODEL_NAME = "clip_text"
MAX_LENGTH = 77  # CLIP standard context length
EMBEDDING_DIM = 768
DEFAULT_OPSET = 17
DEFAULT_MAX_BATCH = 8
COSINE_SIM_THRESHOLD = 0.99


class CLIPTextEncoderWrapper(torch.nn.Module):
    """Wrapper that chains text_model + text_projection.

    ONNX export requires a single nn.Module with a clean forward().
    This wrapper exposes:

        input_ids, attention_mask -> text_model -> pooler_output -> text_projection -> text_embeds
    """

    def __init__(
        self,
        text_model: torch.nn.Module,
        text_projection: torch.nn.Module,
    ) -> None:
        super().__init__()
        self.text_model = text_model
        self.text_projection = text_projection

    def forward(self, input_ids: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
        text_outputs = self.text_model(input_ids=input_ids, attention_mask=attention_mask)
        pooled_output = text_outputs.pooler_output
        text_embeds: torch.Tensor = self.text_projection(pooled_output)
        return text_embeds


def load_clip_model(model_path: str) -> tuple:
    """Load CLIP model and tokenizer from a HuggingFace checkpoint."""
    from transformers import CLIPModel, CLIPTokenizer

    logger.info("Loading CLIP model from %s ...", model_path)
    model = CLIPModel.from_pretrained(model_path)
    model.eval()
    tokenizer = CLIPTokenizer.from_pretrained(model_path)
    logger.info("CLIP model loaded successfully")
    return model, tokenizer


def export_to_onnx(
    model: torch.nn.Module,
    tokenizer: object,
    onnx_path: str,
    *,
    opset: int = DEFAULT_OPSET,
) -> str:
    """Export the CLIP text encoder to ONNX with dynamic batch axis."""
    logger.info("Exporting CLIP text encoder to ONNX ...")
    logger.info("  Output: %s", onnx_path)
    logger.info("  Opset:  %d", opset)

    wrapper = CLIPTextEncoderWrapper(model.text_model, model.text_projection)
    wrapper.eval()

    dummy = tokenizer(
        "a photo of a cat",
        return_tensors="pt",
        padding="max_length",
        max_length=MAX_LENGTH,
    )
    dummy_input_ids = dummy["input_ids"]
    dummy_attention_mask = dummy["attention_mask"]

    Path(onnx_path).parent.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    torch.onnx.export(
        wrapper,
        (dummy_input_ids, dummy_attention_mask),
        onnx_path,
        input_names=["input_ids", "attention_mask"],
        output_names=["text_embeds"],
        dynamic_axes={
            "input_ids": {0: "batch_size"},
            "attention_mask": {0: "batch_size"},
            "text_embeds": {0: "batch_size"},
        },
        opset_version=opset,
        do_constant_folding=True,
    )
    elapsed = time.time() - t0

    size_mb = Path(onnx_path).stat().st_size / (1024 * 1024)
    logger.info("ONNX export complete in %.1fs  (%.1f MB)", elapsed, size_mb)
    return onnx_path


def validate_onnx(
    model: torch.nn.Module,
    tokenizer: object,
    onnx_path: str,
) -> bool:
    """Compare ONNX Runtime output against PyTorch for correctness."""
    try:
        import onnxruntime as ort
    except ImportError as exc:
        raise ImportError(
            "onnxruntime is required for validation. pip install onnxruntime"
        ) from exc

    logger.info("Validating ONNX export against PyTorch ...")

    providers = ["CPUExecutionProvider"]
    session = ort.InferenceSession(onnx_path, providers=providers)

    test_texts = [
        "a photo of a cat",
        "a person walking down the street",
        "security camera footage of a vehicle",
        "an empty parking lot at night",
    ]

    for idx, text in enumerate(test_texts):
        tokens = tokenizer(
            text,
            return_tensors="pt",
            padding="max_length",
            max_length=MAX_LENGTH,
        )
        input_ids = tokens["input_ids"]
        attention_mask = tokens["attention_mask"]

        with torch.no_grad():
            pt_embed = (
                model.get_text_features(input_ids=input_ids, attention_mask=attention_mask)
                .cpu()
                .numpy()
            )

        ort_embed = session.run(
            None,
            {
                "input_ids": input_ids.numpy(),
                "attention_mask": attention_mask.numpy(),
            },
        )[0]

        cos_sim = float(
            np.sum(
                (pt_embed / (np.linalg.norm(pt_embed, axis=-1, keepdims=True) + 1e-8))
                * (ort_embed / (np.linalg.norm(ort_embed, axis=-1, keepdims=True) + 1e-8)),
                axis=-1,
            )[0]
        )

        logger.info("  Test %d  cosine_sim=%.6f  text='%s'", idx + 1, cos_sim, text[:40])

        if cos_sim < COSINE_SIM_THRESHOLD:
            raise ValueError(
                f"Cosine similarity {cos_sim:.6f} is below threshold "
                f"{COSINE_SIM_THRESHOLD} for test text {idx + 1}"
            )

    logger.info("ONNX validation passed (all cosine_sim > %.3f)", COSINE_SIM_THRESHOLD)
    return True


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export CLIP ViT-L/14 text encoder to ONNX for Triton",
    )
    parser.add_argument(
        "--model-path",
        default=os.environ.get("CLIP_MODEL_PATH", "/models/zoo/clip-vit-l"),
        help="Path to HuggingFace CLIP model directory",
    )
    parser.add_argument(
        "--output-path",
        default="/models/cache/clip_text/1/model.onnx",
        help="Output ONNX model path",
    )
    parser.add_argument(
        "--opset",
        type=int,
        default=DEFAULT_OPSET,
        help=f"ONNX opset version (default: {DEFAULT_OPSET})",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip ONNX validation against PyTorch",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    logger.info("=" * 70)
    logger.info("CLIP Text Encoder Export Pipeline")
    logger.info("=" * 70)
    logger.info("  Model path:  %s", args.model_path)
    logger.info("  Output path: %s", args.output_path)
    logger.info("=" * 70)

    model, tokenizer = load_clip_model(args.model_path)

    export_to_onnx(model, tokenizer, args.output_path, opset=args.opset)

    if not args.skip_validation:
        try:
            validate_onnx(model, tokenizer, args.output_path)
        except ImportError:
            logger.warning("onnxruntime not installed -- skipping validation")
        except ValueError as exc:
            logger.error("ONNX validation FAILED: %s", exc)
            import sys

            sys.exit(1)
        except Exception as exc:
            logger.warning(
                "ONNX validation could not complete (non-fatal): %s: %s",
                type(exc).__name__,
                exc,
            )
    else:
        logger.info("Skipping ONNX validation (--skip-validation)")

    logger.info("-" * 70)
    logger.info("Export complete!")
    logger.info("  ONNX: %s", args.output_path)
    logger.info(
        "  Copy to Triton repo: cp %s ai/triton/model_repository/clip_text/1/model.onnx",
        args.output_path,
    )
    logger.info("-" * 70)


if __name__ == "__main__":
    main()
