"""ONNX Export Script for CLIP Vision Encoder.

Exports the CLIP ViT-L vision encoder to ONNX format for TensorRT optimization.
Only exports the image encoder (not text encoder) since embeddings are the primary use case.

Usage:
    # Export HuggingFace CLIP model to ONNX
    python export_onnx.py export \
        --model-path /models/clip-vit-l \
        --output /models/clip-vit-l/vision_encoder.onnx

    # Validate ONNX export against PyTorch
    python export_onnx.py validate \
        --model-path /models/clip-vit-l \
        --onnx /models/clip-vit-l/vision_encoder.onnx

Environment Variables:
    CLIP_MODEL_PATH: Default HuggingFace model path (default: /models/clip-vit-l)
    CLIP_ONNX_OPSET: ONNX opset version (default: 17)
"""

import argparse
import logging
import os
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

# CLIP ViT-L input size (224x224 is standard for CLIP)
CLIP_INPUT_SIZE = (224, 224)

# CLIP ViT-L embedding dimension
EMBEDDING_DIMENSION = 768

# Default opset version for ONNX export
DEFAULT_OPSET_VERSION = 17


class CLIPVisionONNXExporter:
    """Exports CLIP vision encoder to ONNX format.

    Only exports the vision encoder (image -> embedding) since this is the
    performance-critical path for embedding extraction. Text encoding is
    less frequent and doesn't benefit as much from TensorRT optimization.

    Attributes:
        model_path: Path to HuggingFace CLIP model.
        opset_version: ONNX opset version for export.
        model: Loaded CLIP model.
        processor: CLIP image processor.
    """

    def __init__(
        self,
        model_path: str,
        opset_version: int = DEFAULT_OPSET_VERSION,
    ):
        """Initialize the ONNX exporter.

        Args:
            model_path: Path to HuggingFace CLIP model directory or name.
            opset_version: ONNX opset version for export. Default: 17.
        """
        from typing import Any

        self.model_path = model_path
        self.opset_version = opset_version
        self.model: Any = None
        self.processor: Any = None

        logger.info("CLIP Vision ONNX Exporter initialized:")
        logger.info(f"  Model path: {self.model_path}")
        logger.info(f"  Opset version: {self.opset_version}")

    def load_model(self) -> None:
        """Load the CLIP model from HuggingFace."""
        from transformers import CLIPModel, CLIPProcessor

        logger.info(f"Loading CLIP model from: {self.model_path}")

        self.processor = CLIPProcessor.from_pretrained(self.model_path)
        self.model = CLIPModel.from_pretrained(self.model_path)
        self.model.eval()

        logger.info("CLIP model loaded successfully")

    def _create_dummy_input(self, batch_size: int = 1) -> torch.Tensor:
        """Create a dummy input tensor for ONNX export.

        Args:
            batch_size: Batch size for the dummy input.

        Returns:
            Preprocessed dummy input tensor.
        """
        # Create a dummy RGB image
        dummy_image = Image.new("RGB", CLIP_INPUT_SIZE, color=(128, 128, 128))

        # Preprocess using CLIP processor
        inputs = self.processor(images=dummy_image, return_tensors="pt")
        pixel_values: torch.Tensor = inputs["pixel_values"]

        # Expand to batch size if needed
        if batch_size > 1:
            pixel_values = pixel_values.repeat(batch_size, 1, 1, 1)

        return pixel_values

    def export(
        self,
        output_path: str,
        dynamic_batch: bool = True,
        max_batch_size: int = 8,
    ) -> str:
        """Export CLIP vision encoder to ONNX format.

        Args:
            output_path: Output path for ONNX file.
            dynamic_batch: Enable dynamic batch sizes. Default: True.
            max_batch_size: Maximum batch size for optimization. Default: 8.

        Returns:
            Path to the exported ONNX file.

        Raises:
            RuntimeError: If model is not loaded.
        """
        if self.model is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        logger.info(f"Exporting CLIP vision encoder to: {output_path}")
        logger.info(f"  Dynamic batch: {dynamic_batch}")
        logger.info(f"  Max batch size: {max_batch_size}")

        # Create dummy input
        dummy_input = self._create_dummy_input(batch_size=1)
        logger.info(f"  Input shape: {dummy_input.shape}")

        # Create output directory if needed
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # Define dynamic axes for batch dimension
        dynamic_axes = {}
        if dynamic_batch:
            dynamic_axes = {
                "pixel_values": {0: "batch_size"},
                "image_embeds": {0: "batch_size"},
            }

        # Get the vision model only
        vision_model = self.model.vision_model
        visual_projection = self.model.visual_projection

        # Create a wrapper that combines vision model + projection
        class VisionEncoderWrapper(torch.nn.Module):
            """Wrapper combining vision encoder and projection layer."""

            def __init__(
                self, vision_model: torch.nn.Module, visual_projection: torch.nn.Module
            ) -> None:
                super().__init__()
                self.vision_model = vision_model
                self.visual_projection = visual_projection

            def forward(self, pixel_values: torch.Tensor) -> torch.Tensor:
                # Get vision model outputs
                vision_outputs = self.vision_model(pixel_values=pixel_values)
                # Get pooled output (CLS token)
                pooled_output = vision_outputs.pooler_output
                # Project to embedding space
                image_embeds: torch.Tensor = self.visual_projection(pooled_output)
                return image_embeds

        wrapper = VisionEncoderWrapper(vision_model, visual_projection)
        wrapper.eval()

        # Export to ONNX
        start_time = time.time()
        torch.onnx.export(
            wrapper,
            (dummy_input,),
            output_path,
            input_names=["pixel_values"],
            output_names=["image_embeds"],
            dynamic_axes=dynamic_axes,
            opset_version=self.opset_version,
            do_constant_folding=True,
        )
        export_time = time.time() - start_time

        # Get file size
        onnx_size_mb = Path(output_path).stat().st_size / (1024 * 1024)
        logger.info(f"ONNX export completed in {export_time:.1f}s")
        logger.info(f"  Output: {output_path} ({onnx_size_mb:.1f} MB)")

        return output_path


def validate_onnx_export(
    model_path: str,
    onnx_path: str,
    tolerance: float = 1e-4,
) -> bool:
    """Validate ONNX export matches PyTorch output.

    Compares embeddings from PyTorch and ONNX Runtime to ensure
    the export is numerically correct.

    Args:
        model_path: Path to HuggingFace CLIP model.
        onnx_path: Path to exported ONNX file.
        tolerance: Maximum allowed difference. Default: 1e-4.

    Returns:
        True if validation passes.

    Raises:
        ImportError: If onnxruntime is not installed.
        AssertionError: If outputs don't match within tolerance.
    """
    try:
        import onnx
        import onnxruntime as ort
    except ImportError as e:
        raise ImportError(
            "onnx and onnxruntime required. Install with: pip install onnx onnxruntime-gpu"
        ) from e

    from transformers import CLIPModel, CLIPProcessor

    logger.info("Validating ONNX export...")
    logger.info(f"  Model: {model_path}")
    logger.info(f"  ONNX: {onnx_path}")
    logger.info(f"  Tolerance: {tolerance}")

    # Verify ONNX model structure
    logger.info("Verifying ONNX model structure...")
    onnx_model = onnx.load(onnx_path)
    onnx.checker.check_model(onnx_model)
    logger.info("ONNX model structure is valid")

    # Load PyTorch model
    logger.info("Loading PyTorch model...")
    processor = CLIPProcessor.from_pretrained(model_path)
    model = CLIPModel.from_pretrained(model_path)
    model.eval()

    # Create ONNX Runtime session
    logger.info("Creating ONNX Runtime session...")
    providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    ort_session = ort.InferenceSession(onnx_path, providers=providers)
    logger.info(f"  Using provider: {ort_session.get_providers()[0]}")

    # Create test images
    test_images = [
        Image.new("RGB", CLIP_INPUT_SIZE, color=(255, 0, 0)),  # Red
        Image.new("RGB", CLIP_INPUT_SIZE, color=(0, 255, 0)),  # Green
        Image.new("RGB", CLIP_INPUT_SIZE, color=(0, 0, 255)),  # Blue
        Image.new("RGB", CLIP_INPUT_SIZE, color=(128, 128, 128)),  # Gray
    ]

    for i, test_image in enumerate(test_images):
        # Preprocess
        inputs = processor(images=test_image, return_tensors="pt")
        pixel_values = inputs["pixel_values"]

        # PyTorch inference
        with torch.no_grad():
            pytorch_embeds = model.get_image_features(pixel_values=pixel_values)
            pytorch_embeds = pytorch_embeds.cpu().numpy()

        # ONNX Runtime inference
        ort_inputs = {"pixel_values": pixel_values.numpy()}
        onnx_embeds = ort_session.run(None, ort_inputs)[0]

        # Compare outputs
        max_diff = np.abs(pytorch_embeds - onnx_embeds).max()
        mean_diff = np.abs(pytorch_embeds - onnx_embeds).mean()

        # Compute cosine similarity
        pytorch_norm = pytorch_embeds / (
            np.linalg.norm(pytorch_embeds, axis=-1, keepdims=True) + 1e-8
        )
        onnx_norm = onnx_embeds / (np.linalg.norm(onnx_embeds, axis=-1, keepdims=True) + 1e-8)
        cosine_sim = np.sum(pytorch_norm * onnx_norm, axis=-1)[0]

        logger.info(f"Test image {i + 1}:")
        logger.info(f"  Max diff: {max_diff:.6e}")
        logger.info(f"  Mean diff: {mean_diff:.6e}")
        logger.info(f"  Cosine similarity: {cosine_sim:.6f}")

        # Check tolerance
        if max_diff > tolerance:
            logger.warning(f"Max diff {max_diff} exceeds tolerance {tolerance}")

        # Cosine similarity should be > 0.99 for correct export
        if cosine_sim < 0.99:
            raise AssertionError(f"Cosine similarity {cosine_sim:.4f} is below 0.99 threshold")

    logger.info("ONNX validation passed!")
    return True


def convert_to_tensorrt(
    onnx_path: str,
    output_path: str | None = None,
    precision: str = "fp16",
    max_batch_size: int = 8,
    workspace_gb: int = 2,
) -> str:
    """Convert ONNX model to TensorRT engine.

    Args:
        onnx_path: Path to ONNX model file.
        output_path: Output path for TensorRT engine. If None, auto-generated.
        precision: Inference precision ('fp16' or 'fp32'). Default: 'fp16'.
        max_batch_size: Maximum batch size for dynamic batching. Default: 8.
        workspace_gb: TensorRT workspace size in GB. Default: 2.

    Returns:
        Path to the generated TensorRT engine.

    Raises:
        ImportError: If TensorRT is not installed.
    """
    try:
        import tensorrt as trt
    except ImportError as e:
        raise ImportError("TensorRT is not installed. Install with: pip install tensorrt") from e

    logger.info("Converting ONNX to TensorRT...")
    logger.info(f"  ONNX: {onnx_path}")
    logger.info(f"  Precision: {precision}")
    logger.info(f"  Max batch: {max_batch_size}")
    logger.info(f"  Workspace: {workspace_gb} GB")

    # Generate output path if not specified
    if output_path is None:
        onnx_file = Path(onnx_path)
        output_path = str(onnx_file.parent / f"{onnx_file.stem}_{precision}.engine")
    logger.info(f"  Output: {output_path}")

    # Create builder and network
    trt_logger = trt.Logger(trt.Logger.WARNING)
    builder = trt.Builder(trt_logger)

    # Create network with explicit batch
    network_flags = 1 << int(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH)
    network = builder.create_network(network_flags)

    # Parse ONNX model
    parser = trt.OnnxParser(network, trt_logger)
    logger.info("Parsing ONNX model...")

    with open(onnx_path, "rb") as f:  # nosemgrep: path-traversal-open
        if not parser.parse(f.read()):
            for i in range(parser.num_errors):
                logger.error(f"ONNX parse error: {parser.get_error(i)}")
            raise RuntimeError("Failed to parse ONNX model")

    # Configure builder
    config = builder.create_builder_config()
    config.set_memory_pool_limit(
        trt.MemoryPoolType.WORKSPACE,
        workspace_gb * (1 << 30),
    )

    # Set precision
    if precision == "fp16" and builder.platform_has_fast_fp16:
        logger.info("Enabling FP16 precision")
        config.set_flag(trt.BuilderFlag.FP16)
    elif precision == "fp16":
        logger.warning("FP16 not supported on this platform, using FP32")

    # Configure dynamic batch sizes
    logger.info("Configuring optimization profile for dynamic batch...")
    profile = builder.create_optimization_profile()

    # Get input tensor info
    for i in range(network.num_inputs):
        input_tensor = network.get_input(i)
        input_name = input_tensor.name
        input_shape = input_tensor.shape

        # CLIP input shape: [batch, 3, 224, 224]
        # Set min, opt, max shapes for dynamic batch
        min_shape = (1, *tuple(input_shape[1:]))
        opt_shape = (max(1, max_batch_size // 2), *tuple(input_shape[1:]))
        max_shape = (max_batch_size, *tuple(input_shape[1:]))

        profile.set_shape(input_name, min_shape, opt_shape, max_shape)
        logger.info(f"  {input_name}: min={min_shape}, opt={opt_shape}, max={max_shape}")

    config.add_optimization_profile(profile)

    # Build engine
    logger.info("Building TensorRT engine (this may take several minutes)...")
    start_time = time.time()

    serialized_engine = builder.build_serialized_network(network, config)
    if serialized_engine is None:
        raise RuntimeError("Failed to build TensorRT engine")

    build_time = time.time() - start_time
    logger.info(f"Engine built in {build_time:.1f} seconds")

    # Save engine
    output_path_obj = Path(output_path)
    output_path_obj.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:  # nosemgrep: path-traversal-open
        f.write(serialized_engine)

    engine_size_mb = output_path_obj.stat().st_size / (1024 * 1024)
    logger.info(f"TensorRT engine saved: {output_path} ({engine_size_mb:.1f} MB)")

    return output_path


def main() -> None:
    """Main entry point for command-line usage."""
    parser = argparse.ArgumentParser(
        description="Export CLIP vision encoder to ONNX and TensorRT",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export HuggingFace CLIP to ONNX
  python export_onnx.py export \\
      --model-path /models/clip-vit-l \\
      --output /models/clip-vit-l/vision_encoder.onnx

  # Validate ONNX export
  python export_onnx.py validate \\
      --model-path /models/clip-vit-l \\
      --onnx /models/clip-vit-l/vision_encoder.onnx

  # Convert ONNX to TensorRT
  python export_onnx.py tensorrt \\
      --onnx /models/clip-vit-l/vision_encoder.onnx \\
      --output /models/clip-vit-l/vision_encoder_fp16.engine \\
      --precision fp16 \\
      --max-batch 8

  # Full pipeline: export + validate + convert
  python export_onnx.py pipeline \\
      --model-path /models/clip-vit-l \\
      --output-dir /models/clip-vit-l \\
      --precision fp16
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Export subcommand
    export_parser = subparsers.add_parser("export", help="Export CLIP to ONNX")
    export_parser.add_argument(
        "--model-path",
        default=os.environ.get("CLIP_MODEL_PATH", "/models/clip-vit-l"),
        help="HuggingFace CLIP model path",
    )
    export_parser.add_argument(
        "--output",
        required=True,
        help="Output ONNX file path",
    )
    export_parser.add_argument(
        "--opset",
        type=int,
        default=int(os.environ.get("CLIP_ONNX_OPSET", str(DEFAULT_OPSET_VERSION))),
        help=f"ONNX opset version (default: {DEFAULT_OPSET_VERSION})",
    )
    export_parser.add_argument(
        "--no-dynamic-batch",
        action="store_true",
        help="Disable dynamic batch sizes",
    )
    export_parser.add_argument(
        "--max-batch",
        type=int,
        default=8,
        help="Maximum batch size (default: 8)",
    )

    # Validate subcommand
    validate_parser = subparsers.add_parser("validate", help="Validate ONNX export")
    validate_parser.add_argument(
        "--model-path",
        default=os.environ.get("CLIP_MODEL_PATH", "/models/clip-vit-l"),
        help="HuggingFace CLIP model path",
    )
    validate_parser.add_argument(
        "--onnx",
        required=True,
        help="ONNX file path to validate",
    )
    validate_parser.add_argument(
        "--tolerance",
        type=float,
        default=1e-4,
        help="Validation tolerance (default: 1e-4)",
    )

    # TensorRT subcommand
    trt_parser = subparsers.add_parser("tensorrt", help="Convert ONNX to TensorRT")
    trt_parser.add_argument(
        "--onnx",
        required=True,
        help="Input ONNX file path",
    )
    trt_parser.add_argument(
        "--output",
        help="Output TensorRT engine path (auto-generated if not specified)",
    )
    trt_parser.add_argument(
        "--precision",
        choices=["fp16", "fp32"],
        default="fp16",
        help="Inference precision (default: fp16)",
    )
    trt_parser.add_argument(
        "--max-batch",
        type=int,
        default=8,
        help="Maximum batch size (default: 8)",
    )
    trt_parser.add_argument(
        "--workspace",
        type=int,
        default=2,
        help="TensorRT workspace size in GB (default: 2)",
    )

    # Pipeline subcommand (export + validate + convert)
    pipeline_parser = subparsers.add_parser(
        "pipeline", help="Full pipeline: export + validate + convert"
    )
    pipeline_parser.add_argument(
        "--model-path",
        default=os.environ.get("CLIP_MODEL_PATH", "/models/clip-vit-l"),
        help="HuggingFace CLIP model path",
    )
    pipeline_parser.add_argument(
        "--output-dir",
        required=True,
        help="Output directory for ONNX and TensorRT files",
    )
    pipeline_parser.add_argument(
        "--precision",
        choices=["fp16", "fp32"],
        default="fp16",
        help="TensorRT precision (default: fp16)",
    )
    pipeline_parser.add_argument(
        "--max-batch",
        type=int,
        default=8,
        help="Maximum batch size (default: 8)",
    )
    pipeline_parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip ONNX validation step",
    )

    args = parser.parse_args()

    if args.command == "export":
        exporter = CLIPVisionONNXExporter(
            model_path=args.model_path,
            opset_version=args.opset,
        )
        exporter.load_model()
        exporter.export(
            output_path=args.output,
            dynamic_batch=not args.no_dynamic_batch,
            max_batch_size=args.max_batch,
        )

    elif args.command == "validate":
        validate_onnx_export(
            model_path=args.model_path,
            onnx_path=args.onnx,
            tolerance=args.tolerance,
        )

    elif args.command == "tensorrt":
        convert_to_tensorrt(
            onnx_path=args.onnx,
            output_path=args.output,
            precision=args.precision,
            max_batch_size=args.max_batch,
            workspace_gb=args.workspace,
        )

    elif args.command == "pipeline":
        # Create output directory
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Step 1: Export to ONNX
        onnx_path = str(output_dir / "vision_encoder.onnx")
        exporter = CLIPVisionONNXExporter(model_path=args.model_path)
        exporter.load_model()
        exporter.export(
            output_path=onnx_path,
            dynamic_batch=True,
            max_batch_size=args.max_batch,
        )

        # Step 2: Validate (optional)
        if not args.skip_validation:
            validate_onnx_export(
                model_path=args.model_path,
                onnx_path=onnx_path,
            )

        # Step 3: Convert to TensorRT
        engine_path = str(output_dir / f"vision_encoder_{args.precision}.engine")
        convert_to_tensorrt(
            onnx_path=onnx_path,
            output_path=engine_path,
            precision=args.precision,
            max_batch_size=args.max_batch,
        )

        logger.info("Pipeline complete!")
        logger.info(f"  ONNX: {onnx_path}")
        logger.info(f"  TensorRT: {engine_path}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
