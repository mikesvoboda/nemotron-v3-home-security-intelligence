#!/usr/bin/env python3
"""INT8 Post-Training Quantization for Enrichment Models (NEM-5533).

This script quantizes the two heaviest enrichment models to INT8 using
PyTorch native quantization, reducing VRAM from ~2GB to ~550MB combined:
  - Vehicle ResNet-50:  1500MB -> ~400MB  (INT8 static PTQ)
  - Demographics ViT:    500MB -> ~150MB  (INT8 static PTQ)

Usage:
    # Quantize vehicle classifier with calibration images
    python quantize_models.py --model vehicle --calibration-dir /path/to/frames

    # Quantize demographics ViT
    python quantize_models.py --model demographics --calibration-dir /path/to/faces

    # Quantize both models
    python quantize_models.py --model all --calibration-dir /path/to/frames

    # Validate quantized model accuracy
    python quantize_models.py --model vehicle --validate --calibration-dir /path/to/frames

    # Specify output directory
    python quantize_models.py --model vehicle --calibration-dir /path/to/frames \
        --output-dir /models/quantized

Requirements:
    - PyTorch 2.0+ with torch.ao.quantization
    - torchvision (for vehicle ResNet-50)
    - transformers (for demographics ViT)
    - PIL/Pillow (for image loading)

Note:
    INT8 quantization requires a representative calibration dataset to determine
    optimal quantization parameters. Use 100-500 images that represent the expected
    inference distribution (security camera frames for vehicle, face crops for
    demographics).
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

import torch
from PIL import Image
from torch.ao import quantization

# Add parent directories to path for imports
_script_dir = Path(__file__).parent
_enrichment_dir = _script_dir.parent
_ai_dir = _enrichment_dir.parent
_project_root = _ai_dir.parent

for _path in [str(_enrichment_dir), str(_ai_dir), str(_project_root)]:
    if _path not in sys.path:
        sys.path.insert(0, _path)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Default paths matching the model registry defaults
DEFAULT_VEHICLE_MODEL_PATH = os.environ.get(
    "VEHICLE_MODEL_PATH", "/models/vehicle-segment-classification"
)
DEFAULT_AGE_MODEL_PATH = os.environ.get("AGE_MODEL_PATH", "/models/vit-age-classifier")
DEFAULT_OUTPUT_DIR = os.environ.get("QUANTIZED_MODEL_DIR", "/models/quantized")

# Quantization constants
DEFAULT_CALIBRATION_BATCH_SIZE = 32
DEFAULT_NUM_CALIBRATION_BATCHES = 16
MAX_ACCURACY_DELTA_PERCENT = 2.0

# Vehicle model image transforms (must match training)
VEHICLE_IMAGE_SIZE = (224, 224)
VEHICLE_NORMALIZE_MEAN = [0.485, 0.456, 0.406]
VEHICLE_NORMALIZE_STD = [0.229, 0.224, 0.225]

# ViT model image size
VIT_IMAGE_SIZE = (224, 224)


def _get_quantized_model_path(model_name: str, output_dir: str) -> Path:
    """Get the path where a quantized model should be saved.

    Args:
        model_name: Name of the model ("vehicle" or "demographics")
        output_dir: Base output directory for quantized models

    Returns:
        Path to the quantized model file
    """
    output_path = Path(output_dir)
    if model_name == "vehicle":
        return output_path / "vehicle_classifier_int8.pt"
    elif model_name == "demographics":
        return output_path / "demographics_int8.pt"
    else:
        raise ValueError(f"Unknown model name: {model_name}")


def _load_calibration_images(
    calibration_dir: str,
    max_images: int = 500,
) -> list[Image.Image]:
    """Load calibration images from a directory.

    Args:
        calibration_dir: Directory containing calibration images
        max_images: Maximum number of images to load

    Returns:
        List of PIL Images

    Raises:
        FileNotFoundError: If calibration directory doesn't exist
        ValueError: If no valid images found
    """
    cal_path = Path(calibration_dir)
    if not cal_path.exists():
        raise FileNotFoundError(f"Calibration directory not found: {calibration_dir}")

    image_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    image_files = sorted(f for f in cal_path.iterdir() if f.suffix.lower() in image_extensions)

    if not image_files:
        raise ValueError(f"No valid images found in {calibration_dir}")

    image_files = image_files[:max_images]
    logger.info(f"Loading {len(image_files)} calibration images from {calibration_dir}")

    images: list[Image.Image] = []
    for img_path in image_files:
        try:
            img = Image.open(img_path).convert("RGB")
            images.append(img)
        except Exception as e:
            logger.warning(f"Failed to load {img_path}: {e}")

    if not images:
        raise ValueError(f"No images could be loaded from {calibration_dir}")

    logger.info(f"Loaded {len(images)} calibration images")
    return images


# =============================================================================
# Vehicle ResNet-50 Quantization
# =============================================================================


def _load_vehicle_model_fp32(model_path: str) -> tuple[Any, Any]:
    """Load the FP32 vehicle ResNet-50 model.

    Args:
        model_path: Path to vehicle model directory

    Returns:
        Tuple of (model, transform) on CPU in FP32
    """
    from torchvision import models, transforms

    model_dir = Path(model_path)

    # Load class names if available
    classes_file = model_dir / "classes.txt"
    if classes_file.exists():
        classes = classes_file.read_text().splitlines()
        num_classes = len(classes)
    else:
        num_classes = 11  # Default vehicle segment classes

    # Create ResNet-50 architecture
    model = models.resnet50(weights=None)
    num_ftrs = model.fc.in_features
    model.fc = torch.nn.Linear(num_ftrs, num_classes)

    # Load trained weights
    weights_file = model_dir / "pytorch_model.bin"
    if not weights_file.exists():
        raise FileNotFoundError(f"Model weights not found: {weights_file}")

    state_dict = torch.load(weights_file, map_location="cpu", weights_only=True)
    model.load_state_dict(state_dict)
    model.eval()

    # Define transforms (must match training)
    transform = transforms.Compose(
        [
            transforms.Resize(VEHICLE_IMAGE_SIZE),
            transforms.ToTensor(),
            transforms.Normalize(VEHICLE_NORMALIZE_MEAN, VEHICLE_NORMALIZE_STD),
        ]
    )

    logger.info(f"Loaded FP32 vehicle model from {model_path} ({num_classes} classes)")
    return model, transform


def _create_vehicle_calibration_dataloader(
    images: list[Image.Image],
    transform: Any,
    batch_size: int = DEFAULT_CALIBRATION_BATCH_SIZE,
) -> torch.utils.data.DataLoader:
    """Create a DataLoader for vehicle model calibration.

    Args:
        images: List of PIL calibration images
        transform: Image transform pipeline
        batch_size: Batch size for calibration

    Returns:
        DataLoader yielding batches of transformed images
    """

    class CalibrationDataset(torch.utils.data.Dataset):
        def __init__(self, imgs: list[Image.Image], tfm: Any) -> None:
            self.images = imgs
            self.transform = tfm

        def __len__(self) -> int:
            return len(self.images)

        def __getitem__(self, idx: int) -> torch.Tensor:
            img = self.images[idx]
            return self.transform(img)

    dataset = CalibrationDataset(images, transform)
    return torch.utils.data.DataLoader(dataset, batch_size=batch_size, shuffle=False, num_workers=0)


def quantize_vehicle_model(
    model_path: str = DEFAULT_VEHICLE_MODEL_PATH,
    calibration_dir: str | None = None,
    output_dir: str = DEFAULT_OUTPUT_DIR,
    num_calibration_batches: int = DEFAULT_NUM_CALIBRATION_BATCHES,
) -> Path:
    """Quantize the vehicle ResNet-50 classifier to INT8.

    Uses post-training static quantization with representative calibration data.
    ResNet-50 quantizes well with standard per-tensor symmetric quantization
    for weights and per-tensor affine quantization for activations.

    Args:
        model_path: Path to the FP32 vehicle model directory
        calibration_dir: Directory with calibration images (required)
        output_dir: Directory to save the quantized model
        num_calibration_batches: Number of calibration batches to run

    Returns:
        Path to the saved quantized model file

    Raises:
        FileNotFoundError: If model or calibration directory not found
        ValueError: If no calibration images found
    """
    if calibration_dir is None:
        raise ValueError("calibration_dir is required for static quantization")

    logger.info("=== Quantizing Vehicle ResNet-50 to INT8 ===")
    start_time = time.time()

    # Load FP32 model
    model, transform = _load_vehicle_model_fp32(model_path)

    # Prepare calibration data
    images = _load_calibration_images(calibration_dir)
    cal_loader = _create_vehicle_calibration_dataloader(images, transform)

    # Configure quantization for ResNet-50
    # Use fbgemm backend for x86 CPUs (server inference)
    # Per-channel weight quantization for better accuracy
    model.qconfig = quantization.QConfig(
        activation=quantization.HistogramObserver.with_args(
            dtype=torch.quint8,
            reduce_range=True,
        ),
        weight=quantization.PerChannelMinMaxObserver.with_args(
            dtype=torch.qint8,
            qscheme=torch.per_channel_symmetric,
        ),
    )

    # Fuse Conv-BN-ReLU modules for better quantization accuracy
    # ResNet-50 has specific fuseable patterns
    model_fused = quantization.fuse_modules(
        model,
        [
            ["conv1", "bn1", "relu"],
        ],
        inplace=False,
    )

    # Fuse layer blocks (conv-bn pairs in each residual block)
    for layer_name in ["layer1", "layer2", "layer3", "layer4"]:
        layer = getattr(model_fused, layer_name)
        for block_idx in range(len(layer)):
            block = layer[block_idx]
            # Fuse conv-bn pairs in the main path
            fuse_list = []
            if hasattr(block, "conv1") and hasattr(block, "bn1"):
                fuse_list.append(
                    [f"{layer_name}.{block_idx}.conv1", f"{layer_name}.{block_idx}.bn1"]
                )
            if hasattr(block, "conv2") and hasattr(block, "bn2"):
                fuse_list.append(
                    [f"{layer_name}.{block_idx}.conv2", f"{layer_name}.{block_idx}.bn2"]
                )
            if hasattr(block, "conv3") and hasattr(block, "bn3"):
                fuse_list.append(
                    [f"{layer_name}.{block_idx}.conv3", f"{layer_name}.{block_idx}.bn3"]
                )
            # Fuse downsample conv-bn if present
            if hasattr(block, "downsample") and block.downsample is not None:
                if len(block.downsample) >= 2:
                    fuse_list.append(
                        [
                            f"{layer_name}.{block_idx}.downsample.0",
                            f"{layer_name}.{block_idx}.downsample.1",
                        ]
                    )
            if fuse_list:
                model_fused = quantization.fuse_modules(model_fused, fuse_list, inplace=False)

    # Prepare for calibration
    quantization.prepare(model_fused, inplace=True)

    # Run calibration
    logger.info(f"Running calibration with {num_calibration_batches} batches...")
    batch_count = 0
    with torch.inference_mode():
        for batch in cal_loader:
            if batch_count >= num_calibration_batches:
                break
            model_fused(batch)
            batch_count += 1
            if batch_count % 4 == 0:
                logger.info(f"  Calibration batch {batch_count}/{num_calibration_batches}")

    logger.info(f"Calibration complete ({batch_count} batches)")

    # Convert to quantized model
    quantized_model = quantization.convert(model_fused, inplace=False)

    # Save quantized model
    output_path = _get_quantized_model_path("vehicle", output_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(quantized_model.state_dict(), output_path)

    elapsed = time.time() - start_time
    # Report size
    size_mb = output_path.stat().st_size / (1024 * 1024)
    logger.info(f"Quantized vehicle model saved to {output_path} ({size_mb:.1f} MB)")
    logger.info(f"Quantization completed in {elapsed:.1f}s")

    return output_path


# =============================================================================
# Demographics ViT Quantization
# =============================================================================


def _load_demographics_model_fp32(model_path: str) -> tuple[Any, Any]:
    """Load the FP32 demographics ViT model.

    Args:
        model_path: Path to demographics model directory or HuggingFace ID

    Returns:
        Tuple of (model, processor) on CPU in FP32
    """
    from transformers import AutoImageProcessor, ViTForImageClassification

    model_dir = Path(model_path)
    if model_dir.exists():
        local_path = str(model_dir.resolve())
    else:
        local_path = model_path

    processor = AutoImageProcessor.from_pretrained(local_path)
    model = ViTForImageClassification.from_pretrained(local_path)
    model.eval()

    logger.info(f"Loaded FP32 demographics model from {model_path}")
    return model, processor


def quantize_demographics_model(
    model_path: str = DEFAULT_AGE_MODEL_PATH,
    calibration_dir: str | None = None,
    output_dir: str = DEFAULT_OUTPUT_DIR,
    num_calibration_batches: int = DEFAULT_NUM_CALIBRATION_BATCHES,
) -> Path:
    """Quantize the demographics ViT classifier to INT8.

    ViT models require careful quantization due to softmax and GELU activations.
    We use post-training static quantization with histogram-based observers
    that better handle the non-uniform activation distributions in attention layers.

    For ViT-specific handling:
    - Use HistogramObserver for activations (better for attention softmax)
    - Use per-channel quantization for Linear weights
    - Skip quantization of LayerNorm and softmax operations (they need FP32)

    Args:
        model_path: Path to the FP32 demographics model directory
        calibration_dir: Directory with face crop calibration images (required)
        output_dir: Directory to save the quantized model
        num_calibration_batches: Number of calibration batches to run

    Returns:
        Path to the saved quantized model file

    Raises:
        FileNotFoundError: If model or calibration directory not found
        ValueError: If no calibration images found
    """
    if calibration_dir is None:
        raise ValueError("calibration_dir is required for static quantization")

    logger.info("=== Quantizing Demographics ViT to INT8 ===")
    start_time = time.time()

    # Load FP32 model
    model, processor = _load_demographics_model_fp32(model_path)

    # Load calibration images
    images = _load_calibration_images(calibration_dir)

    # Configure quantization for ViT
    # ViT-specific: use HistogramObserver for better handling of attention distributions
    # and MovingAveragePerChannelMinMaxObserver for weights
    vit_qconfig = quantization.QConfig(
        activation=quantization.HistogramObserver.with_args(
            dtype=torch.quint8,
            reduce_range=True,
        ),
        weight=quantization.PerChannelMinMaxObserver.with_args(
            dtype=torch.qint8,
            qscheme=torch.per_channel_symmetric,
        ),
    )

    # Apply quantization config selectively to Linear layers only
    # Skip LayerNorm and attention softmax which need FP32 precision
    for _name, module in model.named_modules():
        if isinstance(module, torch.nn.Linear):
            module.qconfig = vit_qconfig
        elif isinstance(module, torch.nn.LayerNorm):
            # LayerNorm must stay in FP32 for ViT accuracy
            module.qconfig = None

    # Set default qconfig for the model
    model.qconfig = vit_qconfig

    # Insert quantize/dequantize stubs
    model_prepared = quantization.prepare(model, inplace=False)

    # Run calibration
    logger.info(f"Running calibration with {len(images)} images...")
    batch_count = 0
    with torch.inference_mode():
        for i in range(0, len(images), DEFAULT_CALIBRATION_BATCH_SIZE):
            if batch_count >= num_calibration_batches:
                break
            batch_images = images[i : i + DEFAULT_CALIBRATION_BATCH_SIZE]
            inputs = processor(images=batch_images, return_tensors="pt")
            model_prepared(**inputs)
            batch_count += 1
            if batch_count % 4 == 0:
                logger.info(f"  Calibration batch {batch_count}/{num_calibration_batches}")

    logger.info(f"Calibration complete ({batch_count} batches)")

    # Convert to quantized model
    quantized_model = quantization.convert(model_prepared, inplace=False)

    # Save quantized model
    output_path = _get_quantized_model_path("demographics", output_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(quantized_model.state_dict(), output_path)

    elapsed = time.time() - start_time
    size_mb = output_path.stat().st_size / (1024 * 1024)
    logger.info(f"Quantized demographics model saved to {output_path} ({size_mb:.1f} MB)")
    logger.info(f"Quantization completed in {elapsed:.1f}s")

    return output_path


# =============================================================================
# Validation
# =============================================================================


def validate_quantized_model(
    model_name: str,
    model_path: str,
    quantized_model_path: str,
    calibration_dir: str,
    max_accuracy_delta: float = MAX_ACCURACY_DELTA_PERCENT,
) -> dict[str, Any]:
    """Compare INT8 quantized output vs FP32 output on test images.

    Runs both models on the same set of images and compares:
    - Top-1 prediction agreement rate
    - Average confidence delta
    - Maximum confidence delta

    Args:
        model_name: "vehicle" or "demographics"
        model_path: Path to the original FP32 model
        quantized_model_path: Path to the INT8 quantized model file
        calibration_dir: Directory with test images
        max_accuracy_delta: Maximum acceptable accuracy drop (percentage points)

    Returns:
        Dictionary with validation results:
        - agreement_rate: Fraction of images with same top-1 prediction
        - avg_confidence_delta: Average absolute confidence difference
        - max_confidence_delta: Maximum absolute confidence difference
        - passed: Whether accuracy drop is within threshold
        - num_images: Number of images tested

    Raises:
        FileNotFoundError: If model files not found
        ValueError: If unknown model name
    """
    logger.info(f"=== Validating {model_name} INT8 vs FP32 ===")

    images = _load_calibration_images(calibration_dir, max_images=100)

    if model_name == "vehicle":
        return _validate_vehicle(model_path, quantized_model_path, images, max_accuracy_delta)
    elif model_name == "demographics":
        return _validate_demographics(model_path, quantized_model_path, images, max_accuracy_delta)
    else:
        raise ValueError(f"Unknown model name: {model_name}. Use 'vehicle' or 'demographics'.")


def _validate_vehicle(
    model_path: str,
    quantized_model_path: str,
    images: list[Image.Image],
    max_accuracy_delta: float,
) -> dict[str, Any]:
    """Validate vehicle model quantization accuracy.

    Args:
        model_path: Path to FP32 model directory
        quantized_model_path: Path to quantized model state dict
        images: Test images
        max_accuracy_delta: Maximum acceptable accuracy drop

    Returns:
        Validation results dictionary
    """
    from torchvision import models, transforms

    # Load FP32 model
    fp32_model, transform = _load_vehicle_model_fp32(model_path)

    # Load quantized model
    model_dir = Path(model_path)
    classes_file = model_dir / "classes.txt"
    num_classes = len(classes_file.read_text().splitlines()) if classes_file.exists() else 11

    q_model = models.resnet50(weights=None)
    q_model.fc = torch.nn.Linear(q_model.fc.in_features, num_classes)
    q_model.eval()

    # Apply same quantization config and prepare
    q_model.qconfig = quantization.QConfig(
        activation=quantization.HistogramObserver.with_args(
            dtype=torch.quint8,
            reduce_range=True,
        ),
        weight=quantization.PerChannelMinMaxObserver.with_args(
            dtype=torch.qint8,
            qscheme=torch.per_channel_symmetric,
        ),
    )
    q_model = quantization.fuse_modules(q_model, [["conv1", "bn1", "relu"]], inplace=False)
    quantization.prepare(q_model, inplace=True)
    q_model = quantization.convert(q_model, inplace=False)

    # Load quantized weights
    q_state = torch.load(quantized_model_path, map_location="cpu", weights_only=True)
    q_model.load_state_dict(q_state)

    return _compare_models(fp32_model, q_model, images, transform, max_accuracy_delta)


def _validate_demographics(
    model_path: str,
    quantized_model_path: str,
    images: list[Image.Image],
    max_accuracy_delta: float,
) -> dict[str, Any]:
    """Validate demographics model quantization accuracy.

    Args:
        model_path: Path to FP32 model directory
        quantized_model_path: Path to quantized model state dict
        images: Test images
        max_accuracy_delta: Maximum acceptable accuracy drop

    Returns:
        Validation results dictionary
    """
    from transformers import AutoImageProcessor, ViTForImageClassification

    # Load FP32 model
    fp32_model, processor = _load_demographics_model_fp32(model_path)

    # Load quantized model structure
    model_dir = Path(model_path)
    local_path = str(model_dir.resolve()) if model_dir.exists() else model_path
    q_model = ViTForImageClassification.from_pretrained(local_path)
    q_model.eval()

    # Apply quantization config
    vit_qconfig = quantization.QConfig(
        activation=quantization.HistogramObserver.with_args(
            dtype=torch.quint8,
            reduce_range=True,
        ),
        weight=quantization.PerChannelMinMaxObserver.with_args(
            dtype=torch.qint8,
            qscheme=torch.per_channel_symmetric,
        ),
    )
    q_model.qconfig = vit_qconfig
    q_model = quantization.prepare(q_model, inplace=False)
    q_model = quantization.convert(q_model, inplace=False)

    q_state = torch.load(quantized_model_path, map_location="cpu", weights_only=True)
    q_model.load_state_dict(q_state)

    # For ViT, use the processor as the transform
    class ViTTransform:
        def __init__(self, proc: Any) -> None:
            self.processor = proc

        def __call__(self, img: Image.Image) -> torch.Tensor:
            inputs = self.processor(images=img, return_tensors="pt")
            return inputs["pixel_values"].squeeze(0)

    vit_transform = ViTTransform(processor)
    return _compare_models(fp32_model, q_model, images, vit_transform, max_accuracy_delta)


def _compare_models(
    fp32_model: Any,
    int8_model: Any,
    images: list[Image.Image],
    transform: Any,
    max_accuracy_delta: float,
) -> dict[str, Any]:
    """Compare FP32 and INT8 model outputs on the same images.

    Args:
        fp32_model: Original FP32 model
        int8_model: Quantized INT8 model
        images: Test images
        transform: Image transform/preprocessing
        max_accuracy_delta: Maximum acceptable accuracy drop

    Returns:
        Validation results dictionary
    """
    agreements = 0
    confidence_deltas: list[float] = []

    with torch.inference_mode():
        for img in images:
            tensor = transform(img)
            if tensor.dim() == 3:
                tensor = tensor.unsqueeze(0)

            # FP32 inference
            fp32_out = fp32_model(tensor)
            fp32_logits = fp32_out.logits if hasattr(fp32_out, "logits") else fp32_out
            fp32_probs = torch.softmax(fp32_logits, dim=-1)[0]
            fp32_pred = int(fp32_probs.argmax().item())
            fp32_conf = float(fp32_probs[fp32_pred].item())

            # INT8 inference
            int8_out = int8_model(tensor)
            int8_logits = int8_out.logits if hasattr(int8_out, "logits") else int8_out
            int8_probs = torch.softmax(int8_logits, dim=-1)[0]
            int8_pred = int(int8_probs.argmax().item())
            int8_conf = float(int8_probs[int8_pred].item())

            # Compare
            if fp32_pred == int8_pred:
                agreements += 1
            confidence_deltas.append(abs(fp32_conf - int8_conf))

    num_images = len(images)
    agreement_rate = agreements / num_images if num_images > 0 else 0.0
    avg_delta = sum(confidence_deltas) / len(confidence_deltas) if confidence_deltas else 0.0
    max_delta = max(confidence_deltas) if confidence_deltas else 0.0

    # Accuracy drop = 1 - agreement_rate, expressed as percentage
    accuracy_drop_pct = (1.0 - agreement_rate) * 100.0
    passed = accuracy_drop_pct <= max_accuracy_delta

    results = {
        "agreement_rate": round(agreement_rate, 4),
        "accuracy_drop_pct": round(accuracy_drop_pct, 2),
        "avg_confidence_delta": round(avg_delta, 4),
        "max_confidence_delta": round(max_delta, 4),
        "passed": passed,
        "num_images": num_images,
        "threshold_pct": max_accuracy_delta,
    }

    status = "PASSED" if passed else "FAILED"
    logger.info(f"Validation {status}:")
    logger.info(f"  Agreement rate: {agreement_rate:.2%}")
    logger.info(f"  Accuracy drop:  {accuracy_drop_pct:.2f}% (threshold: {max_accuracy_delta}%)")
    logger.info(f"  Avg confidence delta: {avg_delta:.4f}")
    logger.info(f"  Max confidence delta: {max_delta:.4f}")
    logger.info(f"  Images tested: {num_images}")

    if not passed:
        logger.warning(
            f"Quantized model accuracy drop ({accuracy_drop_pct:.2f}%) exceeds "
            f"threshold ({max_accuracy_delta}%). Rejecting quantized model."
        )

    return results


# =============================================================================
# CLI Entry Point
# =============================================================================


def main() -> None:
    """Main CLI entry point for model quantization."""
    parser = argparse.ArgumentParser(
        description="INT8 Post-Training Quantization for Enrichment Models",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Quantize vehicle classifier
  python quantize_models.py --model vehicle --calibration-dir /path/to/frames

  # Quantize demographics ViT
  python quantize_models.py --model demographics --calibration-dir /path/to/faces

  # Quantize both models
  python quantize_models.py --model all --calibration-dir /path/to/frames

  # Validate quantized model accuracy
  python quantize_models.py --model vehicle --validate --calibration-dir /path/to/frames
        """,
    )

    parser.add_argument(
        "--model",
        choices=["vehicle", "demographics", "all"],
        required=True,
        help="Which model to quantize: vehicle (ResNet-50), demographics (ViT), or all",
    )
    parser.add_argument(
        "--calibration-dir",
        required=True,
        help="Directory containing calibration images (100-500 recommended)",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory for quantized models (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--vehicle-model-path",
        default=DEFAULT_VEHICLE_MODEL_PATH,
        help=f"Path to FP32 vehicle model (default: {DEFAULT_VEHICLE_MODEL_PATH})",
    )
    parser.add_argument(
        "--demographics-model-path",
        default=DEFAULT_AGE_MODEL_PATH,
        help=f"Path to FP32 demographics model (default: {DEFAULT_AGE_MODEL_PATH})",
    )
    parser.add_argument(
        "--num-calibration-batches",
        type=int,
        default=DEFAULT_NUM_CALIBRATION_BATCHES,
        help=f"Number of calibration batches (default: {DEFAULT_NUM_CALIBRATION_BATCHES})",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate quantized model accuracy against FP32",
    )
    parser.add_argument(
        "--max-accuracy-delta",
        type=float,
        default=MAX_ACCURACY_DELTA_PERCENT,
        help=f"Maximum acceptable accuracy drop in %% (default: {MAX_ACCURACY_DELTA_PERCENT}%%)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose debug logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    models_to_quantize: list[str] = []
    if args.model == "all":
        models_to_quantize = ["vehicle", "demographics"]
    else:
        models_to_quantize = [args.model]

    for model_name in models_to_quantize:
        if model_name == "vehicle":
            model_path = args.vehicle_model_path
            quantize_fn = quantize_vehicle_model
        else:
            model_path = args.demographics_model_path
            quantize_fn = quantize_demographics_model

        # Quantize
        quantized_path = quantize_fn(
            model_path=model_path,
            calibration_dir=args.calibration_dir,
            output_dir=args.output_dir,
            num_calibration_batches=args.num_calibration_batches,
        )

        # Validate if requested
        if args.validate:
            results = validate_quantized_model(
                model_name=model_name,
                model_path=model_path,
                quantized_model_path=str(quantized_path),
                calibration_dir=args.calibration_dir,
                max_accuracy_delta=args.max_accuracy_delta,
            )
            if not results["passed"]:
                logger.error(
                    f"Quantization validation FAILED for {model_name}. "
                    f"Accuracy drop: {results['accuracy_drop_pct']:.2f}% "
                    f"(max allowed: {args.max_accuracy_delta}%)"
                )
                sys.exit(1)

    logger.info("All quantization tasks completed successfully.")


if __name__ == "__main__":
    main()
