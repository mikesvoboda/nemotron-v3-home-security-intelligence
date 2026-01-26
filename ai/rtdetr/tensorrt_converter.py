"""TensorRT Converter for RT-DETR Models.

Converts ONNX models to TensorRT engines for 2-3x inference speedup.
Supports FP16 and FP32 precision with dynamic batch sizes.

Usage:
    # Convert HuggingFace model to ONNX first
    python tensorrt_converter.py export-onnx \
        --model-path /path/to/hf_model \
        --output /path/to/model.onnx

    # Convert ONNX to TensorRT engine
    python tensorrt_converter.py convert \
        --onnx /path/to/model.onnx \
        --output /path/to/model.engine \
        --precision fp16

Environment Variables:
    RTDETR_TENSORRT_WORKSPACE_GB: TensorRT workspace size in GB (default: 2)
    RTDETR_TENSORRT_MAX_BATCH: Maximum batch size for dynamic batching (default: 1)
"""

import argparse
import logging
import os
import time
from pathlib import Path
from typing import Any

import torch
from PIL import Image

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Valid precision modes
VALID_PRECISIONS = frozenset({"fp16", "fp32"})


class TensorRTConverter:
    """Converts ONNX models to TensorRT engines.

    Attributes:
        onnx_path: Path to the ONNX model file.
        precision: Inference precision ('fp16' or 'fp32').
        max_batch_size: Maximum batch size for dynamic batching.
        dynamic_batch: Whether to enable dynamic batch sizes.
        workspace_size_gb: TensorRT workspace size in GB.
    """

    def __init__(
        self,
        onnx_path: str,
        precision: str = "fp16",
        max_batch_size: int = 1,
        dynamic_batch: bool = False,
        workspace_size_gb: int = 2,
    ):
        """Initialize the TensorRT converter.

        Args:
            onnx_path: Path to the ONNX model file.
            precision: Inference precision ('fp16' or 'fp32'). Default: 'fp16'.
            max_batch_size: Maximum batch size for dynamic batching. Default: 1.
            dynamic_batch: Enable dynamic batch sizes. Default: False.
            workspace_size_gb: TensorRT workspace size in GB. Default: 2.

        Raises:
            ValueError: If precision is not 'fp16' or 'fp32'.
        """
        if precision not in VALID_PRECISIONS:
            raise ValueError(f"precision must be one of {VALID_PRECISIONS}, got '{precision}'")

        self.onnx_path = onnx_path
        self.precision = precision
        self.max_batch_size = max_batch_size
        self.dynamic_batch = dynamic_batch
        self.workspace_size_gb = workspace_size_gb

        logger.info("TensorRT Converter initialized:")
        logger.info(f"  ONNX path: {self.onnx_path}")
        logger.info(f"  Precision: {self.precision}")
        logger.info(f"  Max batch size: {self.max_batch_size}")
        logger.info(f"  Dynamic batch: {self.dynamic_batch}")
        logger.info(f"  Workspace: {self.workspace_size_gb} GB")

    def _get_default_engine_path(self) -> str:
        """Generate default engine path from ONNX path.

        Returns:
            Engine path with precision suffix (e.g., model_fp16.engine).
        """
        onnx_path = Path(self.onnx_path)
        engine_name = f"{onnx_path.stem}_{self.precision}.engine"
        return str(onnx_path.parent / engine_name)

    def _build_engine(self) -> Any:
        """Build TensorRT engine from ONNX model.

        Returns:
            TensorRT engine object.

        Raises:
            ImportError: If TensorRT is not installed.
            RuntimeError: If engine building fails.
        """
        try:
            import tensorrt as trt
        except ImportError as e:
            raise ImportError(
                "TensorRT is not installed. Install with: pip install tensorrt"
            ) from e

        logger.info("Building TensorRT engine...")

        # Create builder and network
        trt_logger = trt.Logger(trt.Logger.WARNING)
        builder = trt.Builder(trt_logger)

        # Create network with explicit batch
        network_flags = 1 << int(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH)
        network = builder.create_network(network_flags)

        # Create ONNX parser
        parser = trt.OnnxParser(network, trt_logger)

        # Parse ONNX model
        logger.info(f"Parsing ONNX model: {self.onnx_path}")
        with open(self.onnx_path, "rb") as f:  # nosemgrep: path-traversal-open
            if not parser.parse(f.read()):
                for i in range(parser.num_errors):
                    logger.error(f"ONNX parse error: {parser.get_error(i)}")
                raise RuntimeError("Failed to parse ONNX model")

        # Configure builder
        config = builder.create_builder_config()
        config.set_memory_pool_limit(
            trt.MemoryPoolType.WORKSPACE,
            self.workspace_size_gb * (1 << 30),  # Convert GB to bytes
        )

        # Set precision
        if self.precision == "fp16" and builder.platform_has_fast_fp16:
            logger.info("Enabling FP16 precision")
            config.set_flag(trt.BuilderFlag.FP16)
        elif self.precision == "fp16":
            logger.warning("FP16 not supported on this platform, using FP32")

        # Configure dynamic batch if enabled
        if self.dynamic_batch:
            logger.info(f"Configuring dynamic batch (max={self.max_batch_size})")
            profile = builder.create_optimization_profile()

            # Get input tensor info
            for i in range(network.num_inputs):
                input_tensor = network.get_input(i)
                input_name = input_tensor.name
                input_shape = input_tensor.shape

                # Set min, opt, max shapes for dynamic batch
                min_shape = (1, *tuple(input_shape[1:]))
                opt_shape = (max(1, self.max_batch_size // 2), *tuple(input_shape[1:]))
                max_shape = (self.max_batch_size, *tuple(input_shape[1:]))

                profile.set_shape(input_name, min_shape, opt_shape, max_shape)
                logger.info(f"  {input_name}: min={min_shape}, opt={opt_shape}, max={max_shape}")

            config.add_optimization_profile(profile)

        # Build engine
        logger.info("Building engine (this may take several minutes)...")
        start_time = time.time()

        serialized_engine = builder.build_serialized_network(network, config)
        if serialized_engine is None:
            raise RuntimeError("Failed to build TensorRT engine")

        build_time = time.time() - start_time
        logger.info(f"Engine built in {build_time:.1f} seconds")

        return serialized_engine

    def export(self, output_path: str | None = None) -> str:
        """Export ONNX model to TensorRT engine.

        Args:
            output_path: Output path for the engine file. If None, generates
                        default path based on ONNX file name.

        Returns:
            Path to the generated engine file.

        Raises:
            FileNotFoundError: If ONNX file doesn't exist.
            RuntimeError: If engine building fails.
        """
        # Validate ONNX file exists
        if not os.path.exists(self.onnx_path):
            raise FileNotFoundError(f"ONNX file not found: {self.onnx_path}")

        # Determine output path
        if output_path is None:
            output_path = self._get_default_engine_path()

        logger.info(f"Exporting TensorRT engine to: {output_path}")

        # Build engine
        serialized_engine = self._build_engine()

        # Save engine
        output_path_obj = Path(output_path)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:  # nosemgrep: path-traversal-open
            f.write(serialized_engine)

        engine_size_mb = output_path_obj.stat().st_size / (1024 * 1024)
        logger.info(f"Engine saved: {output_path} ({engine_size_mb:.1f} MB)")

        return output_path


def export_to_onnx(
    model_path: str,
    output_path: str,
    opset_version: int = 17,
    input_size: tuple[int, int] = (640, 640),
) -> str:
    """Export HuggingFace RT-DETR model to ONNX format.

    Args:
        model_path: Path to HuggingFace model directory or model name.
        output_path: Output path for the ONNX file.
        opset_version: ONNX opset version. Default: 17.
        input_size: Input image size (width, height). Default: (640, 640).

    Returns:
        Path to the generated ONNX file.
    """
    from transformers import AutoImageProcessor, AutoModelForObjectDetection

    logger.info(f"Loading model from: {model_path}")

    # Load model and processor
    processor = AutoImageProcessor.from_pretrained(model_path)
    model = AutoModelForObjectDetection.from_pretrained(model_path)
    model.eval()

    # Create dummy input
    dummy_image = Image.new("RGB", input_size, color=(128, 128, 128))
    inputs = processor(images=dummy_image, return_tensors="pt")

    # Get input tensor
    pixel_values = inputs["pixel_values"]

    logger.info(f"Exporting to ONNX (opset {opset_version})...")
    logger.info(f"  Input shape: {pixel_values.shape}")

    # Export to ONNX
    output_path_obj = Path(output_path)
    output_path_obj.parent.mkdir(parents=True, exist_ok=True)

    torch.onnx.export(
        model,
        (pixel_values,),
        output_path,
        input_names=["pixel_values"],
        output_names=["logits", "pred_boxes"],
        dynamic_axes={
            "pixel_values": {0: "batch_size"},
            "logits": {0: "batch_size"},
            "pred_boxes": {0: "batch_size"},
        },
        opset_version=opset_version,
        do_constant_folding=True,
    )

    onnx_size_mb = output_path_obj.stat().st_size / (1024 * 1024)
    logger.info(f"ONNX model saved: {output_path} ({onnx_size_mb:.1f} MB)")

    return output_path


def verify_onnx(onnx_path: str) -> bool:
    """Verify ONNX model is valid.

    Args:
        onnx_path: Path to ONNX model file.

    Returns:
        True if model is valid.

    Raises:
        ImportError: If onnx package is not installed.
    """
    try:
        import onnx
    except ImportError as e:
        raise ImportError("onnx package not installed. Install with: pip install onnx") from e

    logger.info(f"Verifying ONNX model: {onnx_path}")
    model = onnx.load(onnx_path)
    onnx.checker.check_model(model)
    logger.info("ONNX model verification passed")
    return True


def main():
    """Main entry point for command-line usage."""
    parser = argparse.ArgumentParser(
        description="Convert RT-DETR models to TensorRT engines",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export HuggingFace model to ONNX
  python tensorrt_converter.py export-onnx \\
      --model-path PekingU/rtdetr_r50vd_coco_o365 \\
      --output ./rtdetr.onnx

  # Convert ONNX to TensorRT (FP16)
  python tensorrt_converter.py convert \\
      --onnx ./rtdetr.onnx \\
      --output ./rtdetr_fp16.engine \\
      --precision fp16

  # Convert with dynamic batch support
  python tensorrt_converter.py convert \\
      --onnx ./rtdetr.onnx \\
      --output ./rtdetr_fp16_dynamic.engine \\
      --precision fp16 \\
      --dynamic-batch \\
      --max-batch 8
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # ONNX export subcommand
    onnx_parser = subparsers.add_parser(
        "export-onnx",
        help="Export HuggingFace model to ONNX",
    )
    onnx_parser.add_argument(
        "--model-path",
        required=True,
        help="HuggingFace model path or name",
    )
    onnx_parser.add_argument(
        "--output",
        required=True,
        help="Output ONNX file path",
    )
    onnx_parser.add_argument(
        "--opset",
        type=int,
        default=17,
        help="ONNX opset version (default: 17)",
    )
    onnx_parser.add_argument(
        "--input-size",
        type=int,
        nargs=2,
        default=[640, 640],
        metavar=("WIDTH", "HEIGHT"),
        help="Input image size (default: 640 640)",
    )

    # TensorRT convert subcommand
    trt_parser = subparsers.add_parser(
        "convert",
        help="Convert ONNX to TensorRT engine",
    )
    trt_parser.add_argument(
        "--onnx",
        required=True,
        help="Input ONNX file path",
    )
    trt_parser.add_argument(
        "--output",
        help="Output engine file path (default: auto-generated)",
    )
    trt_parser.add_argument(
        "--precision",
        choices=["fp16", "fp32"],
        default="fp16",
        help="Inference precision (default: fp16)",
    )
    trt_parser.add_argument(
        "--workspace",
        type=int,
        default=int(os.environ.get("RTDETR_TENSORRT_WORKSPACE_GB", "2")),
        help="TensorRT workspace size in GB (default: 2)",
    )
    trt_parser.add_argument(
        "--dynamic-batch",
        action="store_true",
        help="Enable dynamic batch sizes",
    )
    trt_parser.add_argument(
        "--max-batch",
        type=int,
        default=int(os.environ.get("RTDETR_TENSORRT_MAX_BATCH", "1")),
        help="Maximum batch size for dynamic batching (default: 1)",
    )

    # Verify subcommand
    verify_parser = subparsers.add_parser(
        "verify",
        help="Verify ONNX model is valid",
    )
    verify_parser.add_argument(
        "--onnx",
        required=True,
        help="ONNX file path to verify",
    )

    args = parser.parse_args()

    if args.command == "export-onnx":
        export_to_onnx(
            model_path=args.model_path,
            output_path=args.output,
            opset_version=args.opset,
            input_size=tuple(args.input_size),
        )
    elif args.command == "convert":
        converter = TensorRTConverter(
            onnx_path=args.onnx,
            precision=args.precision,
            max_batch_size=args.max_batch,
            dynamic_batch=args.dynamic_batch,
            workspace_size_gb=args.workspace,
        )
        converter.export(args.output)
    elif args.command == "verify":
        verify_onnx(args.onnx)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
