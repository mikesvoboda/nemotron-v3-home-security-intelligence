"""Export Fashion-CLIP (Marqo FashionSigLIP) Vision Encoder to ONNX and TensorRT.

Exports the FashionSigLIP vision encoder used for zero-shot clothing
classification in the enrichment pipeline.  The conversion pipeline mirrors
export_clip.py:

    open_clip PyTorch  -->  ONNX  -->  TensorRT FP16 engine (.plan)

The resulting engine is placed in the Triton model repository layout:
    /models/cache/fashion_clip/1/model.plan

FashionSigLIP is loaded via ``open_clip`` (not ``transformers``) because the
Marqo model wrapper uses meta tensors that cause errors with the standard
HuggingFace AutoModel loader.  See ai/enrichment/model.py line ~920 for the
production loading path.

Architecture note:
    FashionSigLIP uses SigLIP (sigmoid loss) instead of the contrastive loss
    in standard CLIP.  The vision encoder architecture is the same ViT
    structure, so the ONNX export pattern is identical.

Input:  pixel_values  (B, 3, 224, 224)  FP16
Output: embedding     (B, 768)           FP32

L2 normalization is handled by the gateway adapter at serving time, not in
the engine.

Usage:
    # Full pipeline (export + validate + convert)
    python export_fashion_clip.py \\
        --model-path /models/zoo/fashion-clip \\
        --output-path /models/cache/fashion_clip/1/model.plan \\
        --precision fp16

    # ONNX export only
    python export_fashion_clip.py \\
        --model-path /models/zoo/fashion-clip \\
        --output-path /models/cache/fashion_clip/1/model.plan \\
        --onnx-only

    # Use a specific HuggingFace Hub model ID
    python export_fashion_clip.py \\
        --model-path Marqo/marqo-fashionSigLIP \\
        --output-path /models/cache/fashion_clip/1/model.plan
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

import numpy as np
import torch
from PIL import Image

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MODEL_NAME = "fashion_clip"
INPUT_SIZE = (224, 224)  # FashionSigLIP uses 224x224 (same as CLIP ViT-L)
EMBEDDING_DIM = 768  # SigLIP ViT-L embedding dimension
DEFAULT_OPSET = 17
DEFAULT_MAX_BATCH = 8
DEFAULT_WORKSPACE_GB = 1  # Conservative for 4 GB RTX A400
COSINE_SIM_THRESHOLD = 0.999


# ---------------------------------------------------------------------------
# Vision encoder wrapper for open_clip models
# ---------------------------------------------------------------------------


class FashionSigLIPVisionWrapper(torch.nn.Module):
    """Wraps the open_clip vision encoder for clean ONNX export.

    open_clip models expose ``encode_image()`` which internally calls the
    vision tower + projection head.  We replicate that path explicitly so
    ``torch.onnx.export`` can trace it.
    """

    def __init__(self, model: torch.nn.Module) -> None:
        super().__init__()
        self.model = model

    def forward(self, pixel_values: torch.Tensor) -> torch.Tensor:
        # open_clip's encode_image already returns projected embeddings
        image_features: torch.Tensor = self.model.encode_image(pixel_values)
        return image_features


# ---------------------------------------------------------------------------
# Step 1 -- Load model via open_clip
# ---------------------------------------------------------------------------


def _resolve_hub_path(model_path: str) -> str:
    """Convert a local path or HuggingFace model ID to an open_clip hub path.

    Mirrors the resolution logic in ai/enrichment/model.py ClothingClassifier.

    Args:
        model_path: Local directory, HuggingFace model ID, or ``hf-hub:...`` string.

    Returns:
        A string suitable for ``open_clip.create_model_from_pretrained()``.
    """
    if model_path.startswith("hf-hub:"):
        return model_path
    if model_path.startswith("/") or model_path.startswith("./"):
        # Local path -- open_clip needs the hf-hub format for Marqo model
        return "hf-hub:Marqo/marqo-fashionSigLIP"
    if "/" in model_path:
        return f"hf-hub:{model_path}"
    return model_path


def load_fashion_clip_model(model_path: str) -> tuple:
    """Load FashionSigLIP model and preprocessing transform via open_clip.

    Args:
        model_path: Local directory containing model weights, a HuggingFace
            model ID (e.g. ``Marqo/marqo-fashionSigLIP``), or an ``hf-hub:``
            prefixed string.

    Returns:
        Tuple of (open_clip model, preprocess transform).
    """
    from open_clip import create_model_from_pretrained

    hub_path = _resolve_hub_path(model_path)
    logger.info("Loading FashionSigLIP from %s ...", hub_path)

    # Load to CPU first to avoid meta-tensor issues (NEM-5371), then move
    model, preprocess = create_model_from_pretrained(hub_path, device="cpu")
    model.eval()

    logger.info("FashionSigLIP model loaded successfully")
    return model, preprocess


# ---------------------------------------------------------------------------
# Step 2 -- Export to ONNX
# ---------------------------------------------------------------------------


def export_to_onnx(
    model: torch.nn.Module,
    preprocess: object,
    onnx_path: str,
    *,
    opset: int = DEFAULT_OPSET,
    max_batch_size: int = DEFAULT_MAX_BATCH,
) -> str:
    """Export the FashionSigLIP vision encoder to ONNX with dynamic batch axis.

    Args:
        model: The open_clip model.
        preprocess: The image preprocessing transform from open_clip.
        onnx_path: Destination path for the .onnx file.
        opset: ONNX opset version.
        max_batch_size: Maximum batch size (for optimization profile hints).

    Returns:
        The *onnx_path* that was written.
    """
    logger.info("Exporting FashionSigLIP vision encoder to ONNX ...")
    logger.info("  Output:    %s", onnx_path)
    logger.info("  Opset:     %d", opset)
    logger.info("  Max batch: %d", max_batch_size)

    wrapper = FashionSigLIPVisionWrapper(model)
    wrapper.eval()

    # Create a dummy input through the preprocess transform
    dummy_image = Image.new("RGB", INPUT_SIZE, color=(128, 128, 128))
    dummy_input = preprocess(dummy_image).unsqueeze(0)  # (1, 3, 224, 224)
    logger.info("  Input shape: %s", list(dummy_input.shape))

    # Verify the input size matches expectations
    _, c, h, w = dummy_input.shape
    if (h, w) != INPUT_SIZE:
        logger.warning(
            "Preprocessed input size (%d, %d) differs from expected %s.  "
            "Triton config.pbtxt must match the actual size.",
            h,
            w,
            INPUT_SIZE,
        )

    Path(onnx_path).parent.mkdir(parents=True, exist_ok=True)

    dynamic_axes = {
        "pixel_values": {0: "batch_size"},
        "embedding": {0: "batch_size"},
    }

    t0 = time.time()
    torch.onnx.export(
        wrapper,
        (dummy_input,),
        onnx_path,
        input_names=["pixel_values"],
        output_names=["embedding"],
        dynamic_axes=dynamic_axes,
        opset_version=opset,
        do_constant_folding=True,
        dynamo=False,  # Legacy exporter -- embeds weights inline for TRT
    )
    elapsed = time.time() - t0

    size_mb = Path(onnx_path).stat().st_size / (1024 * 1024)
    logger.info("ONNX export complete in %.1fs  (%.1f MB)", elapsed, size_mb)

    # Log actual embedding dim from test inference
    with torch.no_grad():
        test_out = wrapper(dummy_input)
        logger.info("  Output shape: %s  (embedding dim = %d)", list(test_out.shape), test_out.shape[-1])

    return onnx_path


# ---------------------------------------------------------------------------
# Step 3 -- Validate ONNX against PyTorch
# ---------------------------------------------------------------------------


def validate_onnx(
    model: torch.nn.Module,
    preprocess: object,
    onnx_path: str,
) -> bool:
    """Compare ONNX Runtime output against PyTorch for correctness.

    Generates four solid-colour test images, runs inference through both
    backends, and asserts cosine similarity > COSINE_SIM_THRESHOLD.

    Args:
        model: The original open_clip model (PyTorch).
        preprocess: The image preprocessing transform.
        onnx_path: Path to the exported ONNX file.

    Returns:
        True if all tests pass.

    Raises:
        ImportError: If ``onnx`` or ``onnxruntime`` is not installed.
        ValueError: If cosine similarity drops below the threshold.
    """
    try:
        import onnx
        import onnxruntime as ort
    except ImportError as exc:
        raise ImportError(
            "onnx and onnxruntime-gpu are required for validation.  "
            "pip install onnx onnxruntime-gpu"
        ) from exc

    logger.info("Validating ONNX export against PyTorch ...")

    # Structural check
    onnx_model = onnx.load(onnx_path)
    onnx.checker.check_model(onnx_model)
    logger.info("  ONNX structural check passed")

    # Create ORT session
    providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    session = ort.InferenceSession(onnx_path, providers=providers)
    logger.info("  ORT provider: %s", session.get_providers()[0])

    test_colours = [
        (255, 0, 0),
        (0, 255, 0),
        (0, 0, 255),
        (128, 128, 128),
    ]

    for idx, colour in enumerate(test_colours):
        img = Image.new("RGB", INPUT_SIZE, color=colour)
        pixel_values = preprocess(img).unsqueeze(0)  # (1, 3, H, W)

        # PyTorch
        with torch.no_grad():
            pt_embed = model.encode_image(pixel_values).cpu().numpy()

        # ONNX Runtime
        ort_embed = session.run(None, {"pixel_values": pixel_values.numpy()})[0]

        # Metrics
        max_diff = float(np.abs(pt_embed - ort_embed).max())
        cos_sim = float(
            np.sum(
                (pt_embed / (np.linalg.norm(pt_embed, axis=-1, keepdims=True) + 1e-8))
                * (ort_embed / (np.linalg.norm(ort_embed, axis=-1, keepdims=True) + 1e-8)),
                axis=-1,
            )[0]
        )

        logger.info(
            "  Test %d  max_diff=%.2e  cosine_sim=%.6f",
            idx + 1,
            max_diff,
            cos_sim,
        )

        if cos_sim < COSINE_SIM_THRESHOLD:
            raise ValueError(
                f"Cosine similarity {cos_sim:.6f} is below threshold "
                f"{COSINE_SIM_THRESHOLD} for test image {idx + 1}"
            )

    logger.info("ONNX validation passed (all cosine_sim > %.3f)", COSINE_SIM_THRESHOLD)
    return True


# ---------------------------------------------------------------------------
# Step 4 -- Convert ONNX to TensorRT
# ---------------------------------------------------------------------------
# Reuse the same TensorRT conversion logic from export_clip.py to avoid
# duplicating the trtexec / Python API fallback code.


def convert_to_tensorrt(
    onnx_path: str,
    engine_path: str,
    *,
    precision: str = "fp16",
    max_batch_size: int = DEFAULT_MAX_BATCH,
    workspace_gb: int = DEFAULT_WORKSPACE_GB,
) -> str:
    """Convert ONNX to TensorRT, preferring trtexec then falling back to Python API.

    Imports the conversion functions from export_clip.py to share the
    implementation.  If the import fails (e.g. running standalone), falls
    back to a local implementation.

    Args:
        onnx_path: Path to input ONNX model.
        engine_path: Destination for the .plan engine file.
        precision: ``fp16`` or ``fp32``.
        max_batch_size: Maximum dynamic batch size.
        workspace_gb: Workspace memory limit in GB.

    Returns:
        Path to the written engine file.
    """
    try:
        from export_clip import convert_to_tensorrt as _clip_convert

        return _clip_convert(
            onnx_path,
            engine_path,
            precision=precision,
            max_batch_size=max_batch_size,
            workspace_gb=workspace_gb,
        )
    except ImportError:
        pass

    # Fallback: inline implementation identical to export_clip.py
    return _convert_to_tensorrt_inline(
        onnx_path,
        engine_path,
        precision=precision,
        max_batch_size=max_batch_size,
        workspace_gb=workspace_gb,
    )


def _convert_to_tensorrt_inline(
    onnx_path: str,
    engine_path: str,
    *,
    precision: str = "fp16",
    max_batch_size: int = DEFAULT_MAX_BATCH,
    workspace_gb: int = DEFAULT_WORKSPACE_GB,
) -> str:
    """Self-contained TensorRT conversion (trtexec first, then Python API).

    This is a standalone fallback so this script does not strictly depend on
    export_clip.py being importable.
    """
    import shutil
    import subprocess

    def _find_trtexec() -> str | None:
        path = shutil.which("trtexec")
        if path:
            return path
        for candidate in ["/usr/src/tensorrt/bin/trtexec", "/usr/local/bin/trtexec"]:
            if Path(candidate).is_file():
                return candidate
        return None

    trtexec = _find_trtexec()
    if trtexec is not None:
        return _run_trtexec(
            trtexec,
            onnx_path,
            engine_path,
            precision=precision,
            max_batch_size=max_batch_size,
            workspace_gb=workspace_gb,
        )

    return _build_engine_python(
        onnx_path,
        engine_path,
        precision=precision,
        max_batch_size=max_batch_size,
        workspace_gb=workspace_gb,
    )


def _run_trtexec(
    trtexec: str,
    onnx_path: str,
    engine_path: str,
    *,
    precision: str,
    max_batch_size: int,
    workspace_gb: int,
) -> str:
    """Run trtexec subprocess to build the TensorRT engine."""
    import subprocess

    Path(engine_path).parent.mkdir(parents=True, exist_ok=True)

    opt_batch = max(1, max_batch_size // 2)
    min_shape = f"pixel_values:1x3x{INPUT_SIZE[0]}x{INPUT_SIZE[1]}"
    opt_shape = f"pixel_values:{opt_batch}x3x{INPUT_SIZE[0]}x{INPUT_SIZE[1]}"
    max_shape = f"pixel_values:{max_batch_size}x3x{INPUT_SIZE[0]}x{INPUT_SIZE[1]}"

    cmd = [
        trtexec,
        f"--onnx={onnx_path}",
        f"--saveEngine={engine_path}",
        f"--minShapes={min_shape}",
        f"--optShapes={opt_shape}",
        f"--maxShapes={max_shape}",
        f"--workspace={workspace_gb * 1024}",
    ]
    if precision == "fp16":
        cmd.append("--fp16")

    logger.info("Running trtexec: %s", " ".join(cmd))
    t0 = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    elapsed = time.time() - t0

    if result.returncode != 0:
        logger.error("trtexec stdout:\n%s", result.stdout[-2000:] if result.stdout else "")
        logger.error("trtexec stderr:\n%s", result.stderr[-2000:] if result.stderr else "")
        raise RuntimeError(f"trtexec failed with return code {result.returncode}")

    size_mb = Path(engine_path).stat().st_size / (1024 * 1024)
    logger.info("TensorRT engine built in %.1fs  (%.1f MB)", elapsed, size_mb)
    return engine_path


def _build_engine_python(
    onnx_path: str,
    engine_path: str,
    *,
    precision: str,
    max_batch_size: int,
    workspace_gb: int,
) -> str:
    """Build TensorRT engine using the Python tensorrt API."""
    try:
        import tensorrt as trt
    except ImportError as exc:
        raise ImportError("tensorrt Python package required. pip install tensorrt") from exc

    logger.info("Building TensorRT engine via Python API ...")

    trt_logger = trt.Logger(trt.Logger.WARNING)
    builder = trt.Builder(trt_logger)

    network_flags = 1 << int(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH)
    network = builder.create_network(network_flags)

    parser = trt.OnnxParser(network, trt_logger)
    with open(onnx_path, "rb") as f:
        if not parser.parse(f.read()):
            for i in range(parser.num_errors):
                logger.error("ONNX parse error: %s", parser.get_error(i))
            raise RuntimeError("Failed to parse ONNX model")

    config = builder.create_builder_config()
    config.set_memory_pool_limit(trt.MemoryPoolType.WORKSPACE, workspace_gb * (1 << 30))

    if precision == "fp16" and builder.platform_has_fast_fp16:
        config.set_flag(trt.BuilderFlag.FP16)
        logger.info("  FP16 enabled")
    elif precision == "fp16":
        logger.warning("FP16 not supported on this platform -- building FP32")

    profile = builder.create_optimization_profile()
    for i in range(network.num_inputs):
        inp = network.get_input(i)
        name = inp.name
        shape = inp.shape
        min_s = (1, *tuple(shape[1:]))
        opt_s = (max(1, max_batch_size // 2), *tuple(shape[1:]))
        max_s = (max_batch_size, *tuple(shape[1:]))
        profile.set_shape(name, min_s, opt_s, max_s)
        logger.info("  %s: min=%s opt=%s max=%s", name, min_s, opt_s, max_s)
    config.add_optimization_profile(profile)

    t0 = time.time()
    serialized = builder.build_serialized_network(network, config)
    if serialized is None:
        raise RuntimeError("TensorRT engine build returned None")
    elapsed = time.time() - t0

    Path(engine_path).parent.mkdir(parents=True, exist_ok=True)
    with open(engine_path, "wb") as f:
        f.write(serialized)

    size_mb = Path(engine_path).stat().st_size / (1024 * 1024)
    logger.info("TensorRT engine built in %.1fs  (%.1f MB)", elapsed, size_mb)
    return engine_path


# ---------------------------------------------------------------------------
# VRAM estimate
# ---------------------------------------------------------------------------


def estimate_vram(engine_path: str) -> None:
    """Print a rough VRAM estimate for the TensorRT engine.

    Args:
        engine_path: Path to the .plan engine file.
    """
    size_bytes = Path(engine_path).stat().st_size
    size_mb = size_bytes / (1024 * 1024)
    estimated_vram_mb = size_mb + 50
    logger.info("Engine file size:  %.1f MB", size_mb)
    logger.info("Estimated VRAM:    ~%.0f MB  (engine + runtime overhead)", estimated_vram_mb)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Export FashionSigLIP vision encoder to ONNX + TensorRT for Triton",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full pipeline (default)
  python export_fashion_clip.py --model-path /models/zoo/fashion-clip

  # With HuggingFace Hub model ID
  python export_fashion_clip.py --model-path Marqo/marqo-fashionSigLIP

  # ONNX-only (skip TRT conversion)
  python export_fashion_clip.py --model-path /models/zoo/fashion-clip --onnx-only

  # Custom output
  python export_fashion_clip.py \\
      --model-path /models/zoo/fashion-clip \\
      --output-path /models/cache/fashion_clip/1/model.plan \\
      --precision fp16
        """,
    )
    parser.add_argument(
        "--model-path",
        default=os.environ.get("CLOTHING_MODEL_PATH", "/models/zoo/fashion-clip"),
        help="Path to FashionSigLIP model directory or HuggingFace ID "
        "(default: /models/zoo/fashion-clip)",
    )
    parser.add_argument(
        "--output-path",
        default="/models/cache/fashion_clip/1/model.plan",
        help="Output TensorRT engine path (default: /models/cache/fashion_clip/1/model.plan)",
    )
    parser.add_argument(
        "--precision",
        choices=["fp16", "fp32"],
        default="fp16",
        help="TensorRT precision (default: fp16)",
    )
    parser.add_argument(
        "--max-batch",
        type=int,
        default=DEFAULT_MAX_BATCH,
        help=f"Maximum batch size (default: {DEFAULT_MAX_BATCH})",
    )
    parser.add_argument(
        "--workspace-gb",
        type=int,
        default=DEFAULT_WORKSPACE_GB,
        help=f"TensorRT workspace in GB (default: {DEFAULT_WORKSPACE_GB})",
    )
    parser.add_argument(
        "--opset",
        type=int,
        default=DEFAULT_OPSET,
        help=f"ONNX opset version (default: {DEFAULT_OPSET})",
    )
    parser.add_argument(
        "--onnx-only",
        action="store_true",
        help="Export ONNX only, skip TensorRT conversion",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip ONNX validation against PyTorch",
    )
    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    """Run the full export pipeline: Load -> ONNX -> Validate -> TensorRT."""
    args = parse_args(argv)

    logger.info("=" * 70)
    logger.info("FashionSigLIP (Fashion-CLIP) Export Pipeline")
    logger.info("=" * 70)
    logger.info("  Model path:  %s", args.model_path)
    logger.info("  Output path: %s", args.output_path)
    logger.info("  Precision:   %s", args.precision)
    logger.info("  Max batch:   %d", args.max_batch)
    logger.info("=" * 70)

    # ---- Step 1: Load model ------------------------------------------------
    model, preprocess = load_fashion_clip_model(args.model_path)

    # Determine actual input size from the preprocess transform
    dummy_image = Image.new("RGB", INPUT_SIZE, color=(128, 128, 128))
    sample_tensor = preprocess(dummy_image).unsqueeze(0)
    actual_h, actual_w = sample_tensor.shape[2], sample_tensor.shape[3]
    if (actual_h, actual_w) != INPUT_SIZE:
        logger.warning(
            "FashionSigLIP preprocessor produces (%d, %d) -- expected %s.  "
            "Update INPUT_SIZE and Triton config.pbtxt accordingly.",
            actual_h,
            actual_w,
            INPUT_SIZE,
        )

    # Determine embedding dimension from a test forward pass
    with torch.no_grad():
        test_embed = model.encode_image(sample_tensor)
        actual_embed_dim = test_embed.shape[-1]
    if actual_embed_dim != EMBEDDING_DIM:
        logger.warning(
            "FashionSigLIP embedding dim is %d -- expected %d.  "
            "Update EMBEDDING_DIM and Triton config.pbtxt accordingly.",
            actual_embed_dim,
            EMBEDDING_DIM,
        )
    logger.info("  Input:     (%d, 3, %d, %d)", 1, actual_h, actual_w)
    logger.info("  Output:    (%d, %d)", 1, actual_embed_dim)

    # ---- Step 2: Export ONNX -----------------------------------------------
    output_dir = Path(args.output_path).parent
    onnx_path = str(output_dir / "vision_encoder.onnx")

    export_to_onnx(
        model,
        preprocess,
        onnx_path,
        opset=args.opset,
        max_batch_size=args.max_batch,
    )

    # ---- Step 3: Validate --------------------------------------------------
    if not args.skip_validation:
        try:
            validate_onnx(model, preprocess, onnx_path)
        except ImportError:
            logger.warning(
                "onnxruntime not installed -- skipping validation.  "
                "Install with: pip install onnx onnxruntime-gpu"
            )
        except ValueError as exc:
            logger.error("ONNX validation FAILED: %s", exc)
            sys.exit(1)
    else:
        logger.info("Skipping ONNX validation (--skip-validation)")

    # ---- Step 4: Convert to TensorRT --------------------------------------
    if args.onnx_only:
        logger.info("ONNX-only mode -- skipping TensorRT conversion")
        logger.info("ONNX file: %s", onnx_path)
        return

    try:
        engine_path = convert_to_tensorrt(
            onnx_path,
            args.output_path,
            precision=args.precision,
            max_batch_size=args.max_batch,
            workspace_gb=args.workspace_gb,
        )
    except (ImportError, FileNotFoundError, RuntimeError) as exc:
        logger.error("TensorRT conversion failed: %s", exc)
        sys.exit(1)

    # ---- Summary -----------------------------------------------------------
    estimate_vram(engine_path)

    logger.info("-" * 70)
    logger.info("Export complete!")
    logger.info("  ONNX:     %s", onnx_path)
    logger.info("  TensorRT: %s", engine_path)
    logger.info(
        "  Copy to Triton repo:  "
        "cp %s ai/triton/model_repository/fashion_clip/1/model.plan",
        engine_path,
    )
    logger.info("-" * 70)


if __name__ == "__main__":
    main()
