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

    # Full pipeline with INT8 calibration
    python export_onnx.py pipeline \
        --model-path /models/clip-vit-l \
        --output-dir /models/clip-vit-l \
        --precision int8 \
        --calibration-dir /data/calibration/clip

Environment Variables:
    CLIP_MODEL_PATH: Default HuggingFace model path (default: /models/clip-vit-l)
    CLIP_ONNX_OPSET: ONNX opset version (default: 17)
    CLIP_TENSORRT_PRECISION: TensorRT precision (default: fp16)
    CLIP_CALIBRATION_DIR: Path to INT8 calibration images directory
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

# Default TensorRT workspace size in GB (reduced from 2 to 1 for 4GB A400)
DEFAULT_WORKSPACE_GB = 1

# Supported image extensions for calibration dataset
CALIBRATION_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

# Default calibration cache filename
CALIBRATION_CACHE_FILE = "clip_int8_calibration.cache"


class CLIPCalibrationDataset:
    """Provides calibration data for INT8 TensorRT engine building.

    Loads representative images from a directory, preprocesses them using
    CLIP's image processor, and yields batches for TensorRT calibration.
    Implements the ``trt.IInt8EntropyCalibrator2`` interface so TensorRT
    can compute per-tensor dynamic ranges for INT8 quantization.

    The calibration table is cached to disk to avoid recomputation on
    subsequent engine builds with the same calibration data.

    Attributes:
        image_dir: Directory containing calibration images.
        processor: CLIP image processor for preprocessing.
        max_images: Maximum number of images to use for calibration.
        batch_size: Number of images per calibration batch.
        cache_file: Path to the calibration cache file.
        image_paths: List of discovered image file paths.
        current_index: Current position in the image list.
    """

    def __init__(
        self,
        image_dir: str,
        processor: object,
        max_images: int = 500,
        batch_size: int = 1,
        cache_file: str | None = None,
    ) -> None:
        """Initialize the calibration dataset.

        Args:
            image_dir: Directory containing JPEG/PNG images for calibration.
            processor: CLIP image processor (from CLIPProcessor.from_pretrained).
            max_images: Maximum number of images to load. Default: 500.
            batch_size: Number of images per calibration batch. Default: 1.
            cache_file: Path to calibration cache file. If None, defaults to
                ``{image_dir}/clip_int8_calibration.cache``.

        Raises:
            FileNotFoundError: If image_dir does not exist.
            ValueError: If no valid images are found in image_dir.
        """
        self.image_dir = Path(image_dir)
        if not self.image_dir.exists():
            raise FileNotFoundError(f"Calibration image directory not found: {image_dir}")

        self.processor = processor
        self.max_images = max_images
        self.batch_size = batch_size
        self.current_index = 0

        # Set cache file path
        if cache_file is None:
            self.cache_file = str(self.image_dir / CALIBRATION_CACHE_FILE)
        else:
            self.cache_file = cache_file

        # Discover calibration images
        self.image_paths = self._discover_images()
        if not self.image_paths:
            raise ValueError(
                f"No valid images found in {image_dir}. "
                f"Supported formats: {', '.join(sorted(CALIBRATION_IMAGE_EXTENSIONS))}"
            )

        logger.info(f"Calibration dataset initialized: {len(self.image_paths)} images")
        logger.info(f"  Source: {image_dir}")
        logger.info(f"  Cache: {self.cache_file}")

        # Pre-allocate device memory for calibration batch
        # CLIP input: [batch_size, 3, 224, 224] as float32
        self._device_input = np.zeros(
            (self.batch_size, 3, CLIP_INPUT_SIZE[0], CLIP_INPUT_SIZE[1]),
            dtype=np.float32,
        )

    def _discover_images(self) -> list[Path]:
        """Discover and sort calibration images from the image directory.

        Returns:
            Sorted list of image file paths, limited to max_images.
        """
        image_paths: list[Path] = []
        for ext in CALIBRATION_IMAGE_EXTENSIONS:
            image_paths.extend(self.image_dir.glob(f"*{ext}"))
            image_paths.extend(self.image_dir.glob(f"*{ext.upper()}"))

        # Deduplicate (case-insensitive glob on case-insensitive filesystems)
        image_paths = sorted(set(image_paths))

        # Limit to max_images
        if len(image_paths) > self.max_images:
            # Sample evenly across the sorted list for diversity
            step = len(image_paths) / self.max_images
            image_paths = [image_paths[int(i * step)] for i in range(self.max_images)]

        return image_paths

    def _preprocess_image(self, image_path: Path) -> np.ndarray | None:
        """Load and preprocess a single image for calibration.

        Args:
            image_path: Path to the image file.

        Returns:
            Preprocessed image as numpy array of shape (1, 3, 224, 224),
            or None if the image could not be loaded.
        """
        try:
            image = Image.open(image_path).convert("RGB")
            inputs = self.processor(images=image, return_tensors="np")
            pixel_values: np.ndarray = inputs["pixel_values"]
            return pixel_values.astype(np.float32)
        except Exception as e:
            logger.warning(f"Failed to load calibration image {image_path}: {e}")
            return None

    def get_batch_size(self) -> int:
        """Return the calibration batch size.

        Required by TensorRT IInt8EntropyCalibrator2 interface.

        Returns:
            The batch size.
        """
        return self.batch_size

    def get_batch(self, names: list[str] | None = None) -> list[np.ndarray] | None:  # noqa: ARG002
        """Get the next batch of calibration data.

        Required by TensorRT IInt8EntropyCalibrator2 interface.
        Returns preprocessed image batches until all calibration images
        have been consumed.

        Args:
            names: Input tensor names (provided by TensorRT, unused).

        Returns:
            List of numpy arrays (one per input binding) for the next batch,
            or None when calibration is complete.
        """
        if self.current_index >= len(self.image_paths):
            return None

        # Collect batch
        batch_images: list[np.ndarray] = []
        while len(batch_images) < self.batch_size and self.current_index < len(self.image_paths):
            image_path = self.image_paths[self.current_index]
            self.current_index += 1

            preprocessed = self._preprocess_image(image_path)
            if preprocessed is not None:
                batch_images.append(preprocessed)

        if not batch_images:
            return None

        # Stack into batch array
        batch = np.concatenate(batch_images, axis=0)

        # Pad if batch is smaller than batch_size (last batch may be incomplete)
        if batch.shape[0] < self.batch_size:
            padding = np.zeros(
                (self.batch_size - batch.shape[0], *batch.shape[1:]),
                dtype=np.float32,
            )
            batch = np.concatenate([batch, padding], axis=0)

        # Copy to pre-allocated array
        np.copyto(self._device_input, batch)

        if self.current_index % 50 == 0 or self.current_index >= len(self.image_paths):
            logger.info(
                f"  Calibration progress: {self.current_index}/{len(self.image_paths)} images"
            )

        return [self._device_input]

    def read_calibration_cache(self) -> bytes | None:
        """Read the calibration cache from disk if it exists.

        Required by TensorRT IInt8EntropyCalibrator2 interface.
        Returning cached calibration data avoids recomputing dynamic ranges.

        Returns:
            Cached calibration data as bytes, or None if no cache exists.
        """
        if Path(self.cache_file).exists():
            logger.info(f"Reading calibration cache: {self.cache_file}")
            with open(self.cache_file, "rb") as f:  # nosemgrep: path-traversal-open
                return f.read()
        return None

    def write_calibration_cache(self, cache: bytes) -> None:
        """Write calibration data to disk cache.

        Required by TensorRT IInt8EntropyCalibrator2 interface.
        The cache file allows subsequent engine builds to skip calibration.

        Args:
            cache: Calibration data bytes from TensorRT.
        """
        logger.info(f"Writing calibration cache: {self.cache_file}")
        Path(self.cache_file).parent.mkdir(parents=True, exist_ok=True)
        with open(self.cache_file, "wb") as f:  # nosemgrep: path-traversal-open
            f.write(cache)

    def reset(self) -> None:
        """Reset the dataset iterator to the beginning.

        Call this to reuse the dataset for another calibration run.
        """
        self.current_index = 0


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

        # Export to ONNX using legacy exporter (embeds weights inline for TensorRT)
        # PyTorch 2.x dynamo export creates external data files not supported by TensorRT
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
            dynamo=False,  # Force legacy exporter to embed weights inline
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
    workspace_gb: int = DEFAULT_WORKSPACE_GB,
    calibration_dir: str | None = None,
    calibration_cache: str | None = None,
    calibration_max_images: int = 500,
) -> str:
    """Convert ONNX model to TensorRT engine.

    Args:
        onnx_path: Path to ONNX model file.
        output_path: Output path for TensorRT engine. If None, auto-generated.
        precision: Inference precision ('fp16', 'fp32', or 'int8'). Default: 'fp16'.
            INT8 requires a calibration dataset for best accuracy.
        max_batch_size: Maximum batch size for dynamic batching. Default: 8.
        workspace_gb: TensorRT workspace size in GB. Default: 1 (optimized for 4GB A400).
        calibration_dir: Directory containing calibration images for INT8 quantization.
            Only used when precision='int8'. If not provided with INT8 precision,
            TensorRT uses default quantization (less accurate).
        calibration_cache: Path to calibration cache file. If None, auto-generated
            in the calibration_dir. Cached calibration data is reused across builds.
        calibration_max_images: Maximum calibration images to use. Default: 500.

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
    if precision == "int8" and builder.platform_has_fast_int8:
        logger.info("Enabling INT8 precision (with FP16 fallback for sensitive layers)")
        config.set_flag(trt.BuilderFlag.INT8)
        config.set_flag(trt.BuilderFlag.FP16)  # Mixed precision: INT8 + FP16

        # Set up INT8 calibration if calibration directory is provided
        if calibration_dir is not None:
            logger.info(f"  Calibration dir: {calibration_dir}")
            # Load CLIP processor for calibration image preprocessing
            from transformers import CLIPProcessor

            # Determine model path from environment or ONNX path parent
            model_path = os.environ.get("CLIP_MODEL_PATH", "/models/clip-vit-l")
            processor = CLIPProcessor.from_pretrained(model_path)

            calibrator = CLIPCalibrationDataset(
                image_dir=calibration_dir,
                processor=processor,
                max_images=calibration_max_images,
                batch_size=1,
                cache_file=calibration_cache,
            )
            config.int8_calibrator = calibrator
            logger.info(
                f"INT8 calibration: using {len(calibrator.image_paths)} images "
                f"from {calibration_dir}"
            )
        else:
            logger.warning(
                "INT8 precision selected without calibration directory. "
                "TensorRT will use default per-tensor symmetric quantization "
                "which may reduce accuracy by 1-2%. For best results, provide "
                "--calibration-dir with 200-500 representative images."
            )
    elif precision == "int8":
        logger.warning("INT8 not supported on this platform, falling back to FP16")
        if builder.platform_has_fast_fp16:
            config.set_flag(trt.BuilderFlag.FP16)
    elif precision == "fp16" and builder.platform_has_fast_fp16:
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

  # Convert ONNX to TensorRT (FP16)
  python export_onnx.py tensorrt \\
      --onnx /models/clip-vit-l/vision_encoder.onnx \\
      --output /models/clip-vit-l/vision_encoder_fp16.engine \\
      --precision fp16 \\
      --max-batch 8

  # Convert ONNX to TensorRT (INT8 with calibration)
  python export_onnx.py tensorrt \\
      --onnx /models/clip-vit-l/vision_encoder.onnx \\
      --precision int8 \\
      --calibration-dir /data/calibration/clip

  # Full pipeline: export + validate + convert (FP16)
  python export_onnx.py pipeline \\
      --model-path /models/clip-vit-l \\
      --output-dir /models/clip-vit-l \\
      --precision fp16

  # Full pipeline with INT8 calibration
  python export_onnx.py pipeline \\
      --model-path /models/clip-vit-l \\
      --output-dir /models/clip-vit-l \\
      --precision int8 \\
      --calibration-dir /data/calibration/clip
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
        choices=["fp16", "fp32", "int8"],
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
        default=DEFAULT_WORKSPACE_GB,
        help=f"TensorRT workspace size in GB (default: {DEFAULT_WORKSPACE_GB})",
    )
    trt_parser.add_argument(
        "--calibration-dir",
        default=os.environ.get("CLIP_CALIBRATION_DIR"),
        help="Directory containing calibration images for INT8 quantization. "
        "Only used when --precision=int8. Reads CLIP_CALIBRATION_DIR env var if not set.",
    )
    trt_parser.add_argument(
        "--calibration-cache",
        help="Path to calibration cache file (auto-generated if not specified)",
    )
    trt_parser.add_argument(
        "--calibration-max-images",
        type=int,
        default=500,
        help="Maximum number of calibration images to use (default: 500)",
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
        choices=["fp16", "fp32", "int8"],
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
    pipeline_parser.add_argument(
        "--calibration-dir",
        default=os.environ.get("CLIP_CALIBRATION_DIR"),
        help="Directory containing calibration images for INT8 quantization. "
        "Only used when --precision=int8. Reads CLIP_CALIBRATION_DIR env var if not set.",
    )
    pipeline_parser.add_argument(
        "--calibration-cache",
        help="Path to calibration cache file (auto-generated if not specified)",
    )
    pipeline_parser.add_argument(
        "--calibration-max-images",
        type=int,
        default=500,
        help="Maximum number of calibration images to use (default: 500)",
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
            calibration_dir=args.calibration_dir,
            calibration_cache=args.calibration_cache,
            calibration_max_images=args.calibration_max_images,
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
            calibration_dir=args.calibration_dir,
            calibration_cache=args.calibration_cache,
            calibration_max_images=args.calibration_max_images,
        )

        logger.info("Pipeline complete!")
        logger.info(f"  ONNX: {onnx_path}")
        logger.info(f"  TensorRT: {engine_path}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
