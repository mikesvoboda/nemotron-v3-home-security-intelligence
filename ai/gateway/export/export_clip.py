"""Export CLIP ViT-L/14 Vision Encoder to ONNX and TensorRT for Triton Inference Server.

Extracts the vision encoder (vision_model + visual_projection) from the full
CLIP model and converts it through the pipeline:

    HuggingFace PyTorch  -->  ONNX  -->  TensorRT FP16 engine (.plan)

The resulting engine is placed in the Triton model repository layout:
    /models/cache/clip/1/model.plan

This script reuses the same ONNX export + TensorRT conversion pattern from
ai/clip/export_onnx.py, adapted for standalone use in the Triton migration
pipeline (see docs/plans/triton-migration.md, Phase 1).

Input:  pixel_values  (B, 3, 224, 224)  FP16
Output: embedding     (B, 768)           FP32

L2 normalization is NOT applied in the engine -- the gateway adapter handles
that at serving time.

Usage:
    # Full pipeline (export + validate + convert)
    python export_clip.py \\
        --model-path /models/zoo/clip-vit-l \\
        --output-path /models/cache/clip/1/model.plan \\
        --precision fp16

    # ONNX export only
    python export_clip.py \\
        --model-path /models/zoo/clip-vit-l \\
        --output-path /models/cache/clip/1/model.plan \\
        --onnx-only

    # Skip validation (faster, for CI)
    python export_clip.py \\
        --model-path /models/zoo/clip-vit-l \\
        --output-path /models/cache/clip/1/model.plan \\
        --skip-validation
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import subprocess
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

MODEL_NAME = "clip"
INPUT_SIZE = (224, 224)  # CLIP ViT-L standard input resolution
EMBEDDING_DIM = 768  # CLIP ViT-L embedding dimension
DEFAULT_OPSET = 17
DEFAULT_MAX_BATCH = 8
DEFAULT_WORKSPACE_GB = 1  # Conservative for 4 GB RTX A400
COSINE_SIM_THRESHOLD = 0.999  # Minimum acceptable cosine similarity


# ---------------------------------------------------------------------------
# Vision encoder wrapper
# ---------------------------------------------------------------------------


class CLIPVisionEncoderWrapper(torch.nn.Module):
    """Thin wrapper that chains vision_model + visual_projection.

    ONNX export requires a single ``nn.Module`` with a clean ``forward()``.
    This wrapper exposes the combined path:

        pixel_values -> vision_model -> pooler_output -> visual_projection -> embedding
    """

    def __init__(
        self,
        vision_model: torch.nn.Module,
        visual_projection: torch.nn.Module,
    ) -> None:
        super().__init__()
        self.vision_model = vision_model
        self.visual_projection = visual_projection

    def forward(self, pixel_values: torch.Tensor) -> torch.Tensor:
        vision_outputs = self.vision_model(pixel_values=pixel_values)
        pooled_output = vision_outputs.pooler_output
        image_embeds: torch.Tensor = self.visual_projection(pooled_output)
        return image_embeds


# ---------------------------------------------------------------------------
# Step 1 -- Load model from HuggingFace
# ---------------------------------------------------------------------------


def load_clip_model(model_path: str) -> tuple:
    """Load CLIP model and processor from a HuggingFace checkpoint.

    Args:
        model_path: Local directory or HuggingFace model ID containing the
            CLIP ViT-L/14 weights.

    Returns:
        Tuple of (CLIPModel, CLIPProcessor).
    """
    from transformers import CLIPModel, CLIPProcessor

    logger.info("Loading CLIP model from %s ...", model_path)
    processor = CLIPProcessor.from_pretrained(model_path)
    model = CLIPModel.from_pretrained(model_path)
    model.eval()
    logger.info("CLIP model loaded successfully")
    return model, processor


# ---------------------------------------------------------------------------
# Step 2 -- Export to ONNX
# ---------------------------------------------------------------------------


def export_to_onnx(
    model: torch.nn.Module,
    processor: object,
    onnx_path: str,
    *,
    opset: int = DEFAULT_OPSET,
    max_batch_size: int = DEFAULT_MAX_BATCH,
) -> str:
    """Export the CLIP vision encoder to ONNX with dynamic batch axis.

    Args:
        model: Full CLIPModel (vision_model and visual_projection are extracted).
        processor: CLIPProcessor for creating a dummy input.
        onnx_path: Destination path for the .onnx file.
        opset: ONNX opset version.
        max_batch_size: Maximum batch size (used for optimization profile hints).

    Returns:
        The *onnx_path* that was written.
    """
    logger.info("Exporting CLIP vision encoder to ONNX ...")
    logger.info("  Output:    %s", onnx_path)
    logger.info("  Opset:     %d", opset)
    logger.info("  Max batch: %d", max_batch_size)

    # Build the wrapper
    wrapper = CLIPVisionEncoderWrapper(model.vision_model, model.visual_projection)
    wrapper.eval()

    # Create a dummy input through the processor
    dummy_image = Image.new("RGB", INPUT_SIZE, color=(128, 128, 128))
    inputs = processor(images=dummy_image, return_tensors="pt")
    dummy_input: torch.Tensor = inputs["pixel_values"]  # (1, 3, 224, 224)
    logger.info("  Input shape: %s", list(dummy_input.shape))

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
        dynamo=False,  # Force legacy exporter -- embeds weights inline for TRT
    )
    elapsed = time.time() - t0

    size_mb = Path(onnx_path).stat().st_size / (1024 * 1024)
    logger.info("ONNX export complete in %.1fs  (%.1f MB)", elapsed, size_mb)
    return onnx_path


# ---------------------------------------------------------------------------
# Step 3 -- Validate ONNX against PyTorch
# ---------------------------------------------------------------------------


def validate_onnx(
    model: torch.nn.Module,
    processor: object,
    onnx_path: str,
) -> bool:
    """Compare ONNX Runtime output against PyTorch for correctness.

    Generates four solid-colour test images, runs inference through both
    backends, and asserts cosine similarity > COSINE_SIM_THRESHOLD.

    Args:
        model: The original CLIPModel (PyTorch).
        processor: CLIPProcessor for preprocessing.
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
        pixel_values = processor(images=img, return_tensors="pt")["pixel_values"]

        # PyTorch
        with torch.no_grad():
            pt_embed = model.get_image_features(pixel_values=pixel_values).cpu().numpy()

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


def _trtexec_path() -> str | None:
    """Locate the ``trtexec`` binary on the system."""
    path = shutil.which("trtexec")
    if path:
        return path
    # Common container locations
    for candidate in [
        "/usr/src/tensorrt/bin/trtexec",
        "/usr/local/bin/trtexec",
    ]:
        if Path(candidate).is_file():
            return candidate
    return None


def convert_to_tensorrt_trtexec(
    onnx_path: str,
    engine_path: str,
    *,
    precision: str = "fp16",
    max_batch_size: int = DEFAULT_MAX_BATCH,
    workspace_gb: int = DEFAULT_WORKSPACE_GB,
) -> str:
    """Convert ONNX to TensorRT engine using the ``trtexec`` CLI.

    This is the preferred method inside NVIDIA containers where ``trtexec``
    is pre-installed.  Falls back to the Python API if ``trtexec`` is not
    found.

    Args:
        onnx_path: Path to input ONNX model.
        engine_path: Destination for the .plan engine file.
        precision: ``fp16`` or ``fp32``.
        max_batch_size: Maximum dynamic batch size.
        workspace_gb: Workspace memory limit in GB.

    Returns:
        Path to the written engine file.

    Raises:
        FileNotFoundError: If ``trtexec`` is not available.
        RuntimeError: If the conversion process fails.
    """
    trtexec = _trtexec_path()
    if trtexec is None:
        raise FileNotFoundError(
            "trtexec not found. Install TensorRT or use the Python API path."
        )

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
        f"--workspace={workspace_gb * 1024}",  # MiB
    ]

    if precision == "fp16":
        cmd.append("--fp16")

    logger.info("Running trtexec ...")
    logger.info("  Command: %s", " ".join(cmd))

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


def convert_to_tensorrt_python(
    onnx_path: str,
    engine_path: str,
    *,
    precision: str = "fp16",
    max_batch_size: int = DEFAULT_MAX_BATCH,
    workspace_gb: int = DEFAULT_WORKSPACE_GB,
) -> str:
    """Convert ONNX to TensorRT engine using the Python ``tensorrt`` API.

    Used as a fallback when ``trtexec`` is not available.

    Args:
        onnx_path: Path to input ONNX model.
        engine_path: Destination for the .plan engine file.
        precision: ``fp16`` or ``fp32``.
        max_batch_size: Maximum dynamic batch size.
        workspace_gb: Workspace memory limit in GB.

    Returns:
        Path to the written engine file.

    Raises:
        ImportError: If ``tensorrt`` is not installed.
        RuntimeError: If engine building fails.
    """
    try:
        import tensorrt as trt
    except ImportError as exc:
        raise ImportError(
            "tensorrt Python package is required. pip install tensorrt"
        ) from exc

    logger.info("Building TensorRT engine via Python API ...")
    logger.info("  Precision: %s", precision)
    logger.info("  Max batch: %d", max_batch_size)
    logger.info("  Workspace: %d GB", workspace_gb)

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

    # Dynamic batch profile
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


def convert_to_tensorrt(
    onnx_path: str,
    engine_path: str,
    *,
    precision: str = "fp16",
    max_batch_size: int = DEFAULT_MAX_BATCH,
    workspace_gb: int = DEFAULT_WORKSPACE_GB,
) -> str:
    """Convert ONNX to TensorRT, preferring trtexec then falling back to Python API.

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
        return convert_to_tensorrt_trtexec(
            onnx_path,
            engine_path,
            precision=precision,
            max_batch_size=max_batch_size,
            workspace_gb=workspace_gb,
        )
    except FileNotFoundError:
        logger.info("trtexec not found -- falling back to Python tensorrt API")
        return convert_to_tensorrt_python(
            onnx_path,
            engine_path,
            precision=precision,
            max_batch_size=max_batch_size,
            workspace_gb=workspace_gb,
        )


# ---------------------------------------------------------------------------
# VRAM estimate
# ---------------------------------------------------------------------------


def estimate_vram(engine_path: str) -> None:
    """Print a rough VRAM estimate for the TensorRT engine.

    The on-disk engine size is a reasonable proxy for the GPU memory required
    to deserialize it, plus ~50 MB for TensorRT runtime overhead and
    activation scratch space.

    Args:
        engine_path: Path to the .plan engine file.
    """
    size_bytes = Path(engine_path).stat().st_size
    size_mb = size_bytes / (1024 * 1024)
    # TRT runtime overhead + activation buffers typically add 30-80 MB
    estimated_vram_mb = size_mb + 50
    logger.info("Engine file size:  %.1f MB", size_mb)
    logger.info("Estimated VRAM:    ~%.0f MB  (engine + runtime overhead)", estimated_vram_mb)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Export CLIP ViT-L/14 vision encoder to ONNX + TensorRT for Triton",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full pipeline (default)
  python export_clip.py --model-path /models/zoo/clip-vit-l

  # FP32 engine
  python export_clip.py --model-path /models/zoo/clip-vit-l --precision fp32

  # ONNX-only (skip TRT conversion)
  python export_clip.py --model-path /models/zoo/clip-vit-l --onnx-only

  # Custom output path
  python export_clip.py \\
      --model-path /models/zoo/clip-vit-l \\
      --output-path /models/cache/clip/1/model.plan
        """,
    )
    parser.add_argument(
        "--model-path",
        default=os.environ.get("CLIP_MODEL_PATH", "/models/zoo/clip-vit-l"),
        help="Path to HuggingFace CLIP model directory (default: /models/zoo/clip-vit-l)",
    )
    parser.add_argument(
        "--output-path",
        default="/models/cache/clip/1/model.plan",
        help="Output TensorRT engine path (default: /models/cache/clip/1/model.plan)",
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
    logger.info("CLIP ViT-L/14 Export Pipeline")
    logger.info("=" * 70)
    logger.info("  Model path:  %s", args.model_path)
    logger.info("  Output path: %s", args.output_path)
    logger.info("  Precision:   %s", args.precision)
    logger.info("  Max batch:   %d", args.max_batch)
    logger.info("=" * 70)

    # ---- Step 1: Load model ------------------------------------------------
    model, processor = load_clip_model(args.model_path)

    # ---- Step 2: Export ONNX -----------------------------------------------
    output_dir = Path(args.output_path).parent
    onnx_path = str(output_dir / "vision_encoder.onnx")

    export_to_onnx(
        model,
        processor,
        onnx_path,
        opset=args.opset,
        max_batch_size=args.max_batch,
    )

    # ---- Step 3: Validate --------------------------------------------------
    if not args.skip_validation:
        try:
            validate_onnx(model, processor, onnx_path)
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
        "cp %s ai/triton/model_repository/clip/1/model.plan",
        engine_path,
    )
    logger.info("-" * 70)


if __name__ == "__main__":
    main()
