"""Batch Inference Utilities for Model Zoo.

This module provides utilities for true batch inference across Model Zoo models,
enabling efficient GPU utilization by processing multiple images simultaneously
instead of one at a time.

Key features:
- Dynamic batching with configurable batch sizes
- Padding for variable input sizes
- Memory-efficient batch processing
- Support for both classification and detection models

Environment Variables:
- BATCH_SIZE_DEFAULT: Default batch size (default: 8)
- BATCH_SIZE_MAX: Maximum allowed batch size (default: 32)
- BATCH_PADDING_ENABLED: Enable/disable image padding (default: "true")

Usage:
    from batch_utils import BatchProcessor, pad_images_to_batch

    # Process a batch of images
    processor = BatchProcessor(batch_size=8)
    results = processor.process_batch(model, images, inference_fn)

    # Or use direct utility functions
    padded_batch, original_sizes = pad_images_to_batch(images, target_size=(224, 224))

References:
- PyTorch DataLoader: https://pytorch.org/docs/stable/data.html
- Batched Inference: https://huggingface.co/docs/transformers/en/pad_truncation
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
import torch
from numpy.typing import NDArray
from PIL import Image

logger = logging.getLogger(__name__)

# Default batch configuration
DEFAULT_BATCH_SIZE = int(os.environ.get("BATCH_SIZE_DEFAULT", "8"))
MAX_BATCH_SIZE = int(os.environ.get("BATCH_SIZE_MAX", "32"))
PADDING_ENABLED = os.environ.get("BATCH_PADDING_ENABLED", "true").lower() == "true"


@dataclass
class BatchConfig:
    """Configuration for batch processing.

    Attributes:
        batch_size: Number of images per batch
        max_batch_size: Maximum allowed batch size
        pad_to_same_size: Whether to pad images to same size
        target_size: Target size for padding (width, height)
        fill_value: Fill value for padding (0-255)
    """

    batch_size: int = DEFAULT_BATCH_SIZE
    max_batch_size: int = MAX_BATCH_SIZE
    pad_to_same_size: bool = PADDING_ENABLED
    target_size: tuple[int, int] | None = None  # (width, height)
    fill_value: int = 128  # Gray fill for padded areas

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if self.batch_size < 1:
            raise ValueError(f"batch_size must be >= 1, got {self.batch_size}")
        if self.batch_size > self.max_batch_size:
            logger.warning(
                f"batch_size ({self.batch_size}) exceeds max_batch_size ({self.max_batch_size}). "
                f"Clamping to {self.max_batch_size}."
            )
            self.batch_size = self.max_batch_size


@dataclass
class BatchResult:
    """Result from batch processing.

    Attributes:
        results: List of results for each input
        batch_count: Number of batches processed
        total_items: Total number of items processed
        inference_time_ms: Total inference time in milliseconds
    """

    results: list[Any]
    batch_count: int
    total_items: int
    inference_time_ms: float


def chunk_list[T](items: list[T], chunk_size: int) -> Iterator[list[T]]:
    """Split a list into chunks of specified size.

    Args:
        items: List to split
        chunk_size: Size of each chunk

    Yields:
        Chunks of the input list
    """
    for i in range(0, len(items), chunk_size):
        yield items[i : i + chunk_size]


def get_image_size(image: Image.Image | NDArray[np.uint8]) -> tuple[int, int]:
    """Get the size of an image.

    Args:
        image: PIL Image or numpy array

    Returns:
        Tuple of (width, height)
    """
    if isinstance(image, Image.Image):
        return image.size  # (width, height)
    else:
        # numpy array is (height, width, channels)
        return (image.shape[1], image.shape[0])


def compute_batch_target_size(
    images: list[Image.Image | NDArray[np.uint8]],
    fixed_size: tuple[int, int] | None = None,
) -> tuple[int, int]:
    """Compute the target size for a batch of images.

    If fixed_size is provided, uses that. Otherwise, computes the maximum
    dimensions across all images in the batch.

    Args:
        images: List of images
        fixed_size: Optional fixed target size (width, height)

    Returns:
        Target size (width, height) for the batch
    """
    if fixed_size is not None:
        return fixed_size

    if not images:
        raise ValueError("Cannot compute target size for empty image list")

    max_width = 0
    max_height = 0

    for img in images:
        w, h = get_image_size(img)
        max_width = max(max_width, w)
        max_height = max(max_height, h)

    return (max_width, max_height)


def pad_image(
    image: Image.Image | NDArray[np.uint8],
    target_size: tuple[int, int],
    fill_value: int = 128,
) -> tuple[Image.Image, tuple[int, int]]:
    """Pad an image to target size with center alignment.

    Args:
        image: Input image (PIL Image or numpy array)
        target_size: Target size (width, height)
        fill_value: Fill value for padding (0-255)

    Returns:
        Tuple of (padded PIL Image, original size (width, height))
    """
    # Convert numpy array to PIL Image if needed
    if isinstance(image, np.ndarray):
        image = Image.fromarray(image)

    original_size = image.size  # (width, height)
    target_width, target_height = target_size

    # If already the right size, return as-is
    if original_size[0] == target_width and original_size[1] == target_height:
        return image, original_size

    # Create padded image with fill color
    padded = Image.new("RGB", target_size, color=(fill_value, fill_value, fill_value))

    # Calculate paste position (center alignment)
    paste_x = (target_width - original_size[0]) // 2
    paste_y = (target_height - original_size[1]) // 2

    # Paste original image onto padded canvas
    padded.paste(image.convert("RGB"), (paste_x, paste_y))

    return padded, original_size


def pad_images_to_batch(
    images: list[Image.Image | NDArray[np.uint8]],
    target_size: tuple[int, int] | None = None,
    fill_value: int = 128,
) -> tuple[list[Image.Image], list[tuple[int, int]]]:
    """Pad a list of images to the same size for batch processing.

    Args:
        images: List of images to pad
        target_size: Optional fixed target size. If None, uses max dimensions.
        fill_value: Fill value for padding (0-255)

    Returns:
        Tuple of (list of padded images, list of original sizes)
    """
    if not images:
        return [], []

    # Compute target size
    batch_target_size = compute_batch_target_size(images, target_size)

    padded_images: list[Image.Image] = []
    original_sizes: list[tuple[int, int]] = []

    for img in images:
        padded, orig_size = pad_image(img, batch_target_size, fill_value)
        padded_images.append(padded)
        original_sizes.append(orig_size)

    return padded_images, original_sizes


def unpad_result(
    result: dict[str, Any],
    original_size: tuple[int, int],
    padded_size: tuple[int, int],
) -> dict[str, Any]:
    """Adjust bounding box coordinates from padded to original image space.

    Args:
        result: Detection result with 'bbox' key
        original_size: Original image size (width, height)
        padded_size: Padded image size (width, height)

    Returns:
        Result with adjusted bounding box coordinates
    """
    if "bbox" not in result:
        return result

    # Calculate padding offsets
    pad_x = (padded_size[0] - original_size[0]) // 2
    pad_y = (padded_size[1] - original_size[1]) // 2

    bbox = result["bbox"]
    adjusted_bbox: dict[str, Any] | list[Any] | tuple[Any, ...] | Any

    # Handle different bbox formats (dict with x/y/width/height or list [x1, y1, x2, y2])
    if isinstance(bbox, dict):
        adjusted_bbox_dict: dict[str, Any] = {
            "x": max(0, bbox["x"] - pad_x),
            "y": max(0, bbox["y"] - pad_y),
            "width": bbox["width"],
            "height": bbox["height"],
        }
        # Clamp to original image bounds
        adjusted_bbox_dict["width"] = min(
            adjusted_bbox_dict["width"], original_size[0] - adjusted_bbox_dict["x"]
        )
        adjusted_bbox_dict["height"] = min(
            adjusted_bbox_dict["height"], original_size[1] - adjusted_bbox_dict["y"]
        )
        adjusted_bbox = adjusted_bbox_dict
    elif isinstance(bbox, list | tuple):
        if len(bbox) == 4:
            # Interpret as [x1, y1, x2, y2] format
            adjusted_bbox = [
                max(0, bbox[0] - pad_x),
                max(0, bbox[1] - pad_y),
                min(original_size[0], bbox[2] - pad_x),
                min(original_size[1], bbox[3] - pad_y),
            ]
        else:
            adjusted_bbox = bbox
    else:
        adjusted_bbox = bbox

    return {**result, "bbox": adjusted_bbox}


class BatchProcessor:
    """Batch processor for efficient multi-image inference.

    This class provides utilities for processing multiple images in batches,
    with support for dynamic batching, padding, and result aggregation.

    Attributes:
        config: Batch processing configuration
    """

    def __init__(
        self,
        batch_size: int = DEFAULT_BATCH_SIZE,
        config: BatchConfig | None = None,
    ) -> None:
        """Initialize batch processor.

        Args:
            batch_size: Number of images per batch (used if config not provided)
            config: Full batch configuration (overrides batch_size)
        """
        if config is not None:
            self.config = config
        else:
            self.config = BatchConfig(batch_size=batch_size)

    def process_batch(
        self,
        images: list[Image.Image | NDArray[np.uint8]],
        inference_fn: Callable[[Sequence[Image.Image | NDArray[np.uint8]]], list[Any]],
        pad_images: bool | None = None,
        target_size: tuple[int, int] | None = None,
    ) -> BatchResult:
        """Process images in batches using the provided inference function.

        Args:
            images: List of images to process
            inference_fn: Function that takes a list of images and returns results
            pad_images: Whether to pad images to same size (uses config if None)
            target_size: Optional fixed target size for padding

        Returns:
            BatchResult with all results and timing information
        """
        import time

        start_time = time.perf_counter()

        if not images:
            return BatchResult(
                results=[],
                batch_count=0,
                total_items=0,
                inference_time_ms=0.0,
            )

        # Determine padding behavior
        should_pad = pad_images if pad_images is not None else self.config.pad_to_same_size
        use_target_size = target_size or self.config.target_size

        all_results: list[Any] = []
        batch_count = 0

        # Process in batches
        for batch in chunk_list(images, self.config.batch_size):
            batch_count += 1

            if should_pad:
                # Pad images to same size
                padded_batch, original_sizes = pad_images_to_batch(
                    batch,
                    target_size=use_target_size,
                    fill_value=self.config.fill_value,
                )
                batch_target_size = get_image_size(padded_batch[0]) if padded_batch else (0, 0)

                # Run inference
                batch_results = inference_fn(padded_batch)

                # Unpad results if they contain bounding boxes
                for i, result in enumerate(batch_results):
                    if isinstance(result, dict) and "bbox" in result:
                        batch_results[i] = unpad_result(
                            result, original_sizes[i], batch_target_size
                        )
                    elif isinstance(result, list):
                        # Handle list of detections
                        batch_results[i] = [
                            unpad_result(r, original_sizes[i], batch_target_size)
                            if isinstance(r, dict) and "bbox" in r
                            else r
                            for r in result
                        ]
            else:
                # Process without padding
                batch_results = inference_fn(batch)

            all_results.extend(batch_results)

        inference_time_ms = (time.perf_counter() - start_time) * 1000

        return BatchResult(
            results=all_results,
            batch_count=batch_count,
            total_items=len(images),
            inference_time_ms=inference_time_ms,
        )

    def process_with_preprocessing(
        self,
        images: list[Image.Image | NDArray[np.uint8]],
        preprocess_fn: Callable[[list[Image.Image]], torch.Tensor],
        model: torch.nn.Module,
        postprocess_fn: Callable[[torch.Tensor, list[Image.Image]], list[Any]],
        device: str = "cuda:0",
    ) -> BatchResult:
        """Process images with custom preprocessing and postprocessing.

        This method provides more control over the batch processing pipeline,
        allowing custom preprocessing (e.g., normalization, augmentation)
        and postprocessing (e.g., NMS, thresholding).

        Args:
            images: List of images to process
            preprocess_fn: Function to preprocess images into tensor
            model: PyTorch model for inference
            postprocess_fn: Function to postprocess model outputs
            device: Device to run inference on

        Returns:
            BatchResult with all results and timing information
        """
        import time

        start_time = time.perf_counter()

        if not images:
            return BatchResult(
                results=[],
                batch_count=0,
                total_items=0,
                inference_time_ms=0.0,
            )

        all_results: list[Any] = []
        batch_count = 0

        for batch in chunk_list(images, self.config.batch_size):
            batch_count += 1

            # Convert numpy arrays to PIL Images
            pil_batch = [
                Image.fromarray(img) if isinstance(img, np.ndarray) else img for img in batch
            ]

            # Preprocess
            input_tensor = preprocess_fn(pil_batch)

            # Move to device
            if isinstance(input_tensor, torch.Tensor):
                input_tensor = input_tensor.to(device)
            elif isinstance(input_tensor, dict):
                input_tensor = {k: v.to(device) for k, v in input_tensor.items()}

            # Run inference
            with torch.no_grad():
                if isinstance(input_tensor, dict):
                    outputs = model(**input_tensor)
                else:
                    outputs = model(input_tensor)

            # Postprocess
            batch_results = postprocess_fn(outputs, pil_batch)
            all_results.extend(batch_results)

        inference_time_ms = (time.perf_counter() - start_time) * 1000

        return BatchResult(
            results=all_results,
            batch_count=batch_count,
            total_items=len(images),
            inference_time_ms=inference_time_ms,
        )


def create_batch_inference_fn(
    model: torch.nn.Module,
    processor: Any,
    device: str = "cuda:0",
    post_process_fn: Callable[[Any, list[Image.Image]], list[Any]] | None = None,
) -> Callable[[list[Image.Image]], list[Any]]:
    """Create a batch inference function for a model with HuggingFace processor.

    This factory function creates a ready-to-use batch inference function
    that handles preprocessing, inference, and optional postprocessing.

    Args:
        model: PyTorch model (e.g., from transformers)
        processor: HuggingFace processor for the model
        device: Device to run inference on
        post_process_fn: Optional function to post-process outputs

    Returns:
        Function that takes a list of images and returns a list of results
    """

    def batch_inference(images: list[Image.Image]) -> list[Any]:
        if not images:
            return []

        # Ensure all images are RGB PIL Images
        pil_images = [
            img.convert("RGB")
            if isinstance(img, Image.Image)
            else Image.fromarray(img).convert("RGB")
            for img in images
        ]

        # Preprocess batch
        inputs = processor(images=pil_images, return_tensors="pt", padding=True)

        # Move to device with correct dtype
        model_dtype = next(model.parameters()).dtype
        inputs = {k: v.to(device, model_dtype) for k, v in inputs.items()}

        # Run inference
        with torch.no_grad():
            outputs = model(**inputs)

        # Post-process if function provided
        if post_process_fn is not None:
            return post_process_fn(outputs, pil_images)

        # Default: return raw outputs split per image
        if hasattr(outputs, "logits"):
            return [outputs.logits[i].cpu() for i in range(len(images))]
        return [outputs]

    return batch_inference
