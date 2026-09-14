"""Privacy masking service using instance segmentation (NEM-3912).

This module provides privacy masking capabilities using segmentation masks from
YOLO26 instance segmentation. It supports multiple masking strategies for
obscuring detected persons and other privacy-sensitive objects.

Privacy Features:
    - Blur masking: Gaussian blur applied to masked regions
    - Solid color masking: Fill masked regions with a solid color
    - Pixelation: Downscale and upscale to create pixelated effect

Re-ID Improvement Features:
    - Foreground extraction: Extract only the detected entity with black background
    - Cropped region extraction: Crop just the masked region for embedding generation

Usage:
    service = get_privacy_masking_service()

    # Apply blur to detected persons
    masked_image = service.mask_detections(
        image=original_image,
        detections=yolo_detections,
        strategy=MaskingStrategy.BLUR,
        class_filter=["person"],
    )

    # Extract foreground for better Re-ID embeddings
    foreground = service.extract_foreground(
        image=original_image,
        mask=person_mask,
        background_color=(0, 0, 0),
    )
"""

from __future__ import annotations

from enum import Enum
from typing import Any

import numpy as np
from PIL import Image, ImageFilter

from backend.core.logging import get_logger

logger = get_logger(__name__)


class MaskingStrategy(str, Enum):
    """Available masking strategies for privacy protection."""

    BLUR = "blur"
    SOLID = "solid"
    PIXELATE = "pixelate"


class PrivacyMaskingService:
    """Service for applying privacy masks to images using segmentation data.

    This service takes segmentation masks from YOLO26 instance segmentation
    and applies various masking strategies to obscure detected objects for
    privacy protection or to improve Re-ID embedding quality.

    Attributes:
        default_strategy: Default masking strategy to use
        blur_radius: Radius for Gaussian blur (default: 25)
        pixelate_size: Block size for pixelation (default: 10)
    """

    def __init__(
        self,
        default_strategy: MaskingStrategy = MaskingStrategy.BLUR,
        blur_radius: int = 25,
        pixelate_size: int = 10,
    ) -> None:
        """Initialize the privacy masking service.

        Args:
            default_strategy: Default masking strategy
            blur_radius: Radius for Gaussian blur effect
            pixelate_size: Block size for pixelation effect
        """
        self.default_strategy = default_strategy
        self.blur_radius = blur_radius
        self.pixelate_size = pixelate_size

        logger.info(
            "PrivacyMaskingService initialized with strategy=%s, blur_radius=%d, pixelate_size=%d",
            default_strategy.value,
            blur_radius,
            pixelate_size,
        )

    def apply_mask(
        self,
        image: Image.Image,
        mask: np.ndarray,
        strategy: MaskingStrategy | None = None,
        fill_color: tuple[int, int, int] = (0, 0, 0),
        invert: bool = False,
    ) -> Image.Image:
        """Apply a masking effect to regions of an image.

        Args:
            image: Source PIL Image
            mask: Binary mask array (0/255 or 0/1) where non-zero indicates mask
            strategy: Masking strategy to use (defaults to self.default_strategy)
            fill_color: Color for solid masking (default black)
            invert: If True, mask the background instead of foreground

        Returns:
            New image with mask applied
        """
        if strategy is None:
            strategy = self.default_strategy

        # Ensure mask is binary (0 or 255)
        binary_mask = ((mask > 0) * 255).astype(np.uint8)

        # Invert mask if requested (mask background, keep foreground)
        if invert:
            binary_mask = 255 - binary_mask

        # Convert mask to PIL Image for compositing
        mask_image = Image.fromarray(binary_mask, mode="L")

        # Apply the selected masking strategy
        if strategy == MaskingStrategy.BLUR:
            return self._apply_blur_mask(image, mask_image)
        elif strategy == MaskingStrategy.SOLID:
            return self._apply_solid_mask(image, mask_image, fill_color)
        elif strategy == MaskingStrategy.PIXELATE:
            return self._apply_pixelate_mask(image, mask_image)
        else:
            logger.warning(f"Unknown masking strategy: {strategy}, using blur")
            return self._apply_blur_mask(image, mask_image)

    def _apply_blur_mask(self, image: Image.Image, mask_image: Image.Image) -> Image.Image:
        """Apply Gaussian blur to masked regions."""
        # Create blurred version of entire image
        blurred = image.filter(ImageFilter.GaussianBlur(radius=self.blur_radius))

        # Composite: use blurred image where mask is white, original elsewhere
        return Image.composite(blurred, image, mask_image)

    def _apply_solid_mask(
        self,
        image: Image.Image,
        mask_image: Image.Image,
        fill_color: tuple[int, int, int],
    ) -> Image.Image:
        """Apply solid color to masked regions."""
        # Create solid color image
        solid = Image.new("RGB", image.size, fill_color)

        # Composite: use solid color where mask is white, original elsewhere
        return Image.composite(solid, image, mask_image)

    def _apply_pixelate_mask(self, image: Image.Image, mask_image: Image.Image) -> Image.Image:
        """Apply pixelation effect to masked regions."""
        # Create pixelated version by downscaling and upscaling
        small_size = (
            max(1, image.size[0] // self.pixelate_size),
            max(1, image.size[1] // self.pixelate_size),
        )
        pixelated = image.resize(small_size, Image.Resampling.NEAREST)
        pixelated = pixelated.resize(image.size, Image.Resampling.NEAREST)

        # Composite: use pixelated where mask is white, original elsewhere
        return Image.composite(pixelated, image, mask_image)

    def invert_mask(self, mask: np.ndarray) -> np.ndarray:
        """Invert a binary mask.

        Args:
            mask: Binary mask array

        Returns:
            Inverted mask where foreground becomes background and vice versa
        """
        # Ensure binary (0 or 255)
        binary_mask = ((mask > 0) * 255).astype(np.uint8)
        return 255 - binary_mask

    def decode_rle_mask(self, rle: dict[str, Any]) -> np.ndarray:
        """Decode run-length encoding to binary mask.

        Args:
            rle: Dictionary with 'counts' and 'size' keys

        Returns:
            Binary numpy array mask
        """
        height, width = rle["size"]
        counts = rle["counts"]

        # Reconstruct flat mask from RLE
        flat = np.zeros(height * width, dtype=np.uint8)
        pos = 0
        value = 0  # Start with zeros

        for count in counts:
            flat[pos : pos + count] = value
            pos += count
            value = 1 - value  # Toggle between 0 and 1

        # Reshape to original dimensions (column-major order for COCO)
        return flat.reshape((height, width), order="F")

    def combine_masks(self, masks: list[np.ndarray]) -> np.ndarray:
        """Combine multiple masks into a single mask using logical OR.

        Args:
            masks: List of binary mask arrays (must all be same shape)

        Returns:
            Combined mask where any mask=1 results in combined=1
        """
        if not masks:
            raise ValueError("At least one mask is required")

        # Start with zeros and OR each mask
        combined = np.zeros_like(masks[0], dtype=np.uint8)
        for mask in masks:
            combined = np.logical_or(combined, mask > 0).astype(np.uint8)

        return combined * 255  # Convert to 0/255 for PIL compatibility

    def mask_detections(
        self,
        image: Image.Image,
        detections: list[dict[str, Any]],
        strategy: MaskingStrategy | None = None,
        fill_color: tuple[int, int, int] = (0, 0, 0),
        class_filter: list[str] | None = None,
    ) -> Image.Image:
        """Apply masking to multiple detections at once.

        Args:
            image: Source PIL Image
            detections: List of detection dicts with mask_rle data
            strategy: Masking strategy to use
            fill_color: Color for solid masking
            class_filter: If provided, only mask these classes

        Returns:
            Image with all matching detections masked
        """
        # Filter detections if class_filter is provided
        if class_filter:
            detections = [d for d in detections if d.get("class") in class_filter]

        if not detections:
            return image.copy()

        # Collect and decode all masks
        masks = []
        for detection in detections:
            mask_rle = detection.get("mask_rle")
            if mask_rle is not None:
                try:
                    mask = self.decode_rle_mask(mask_rle)
                    # Resize mask if needed to match image size
                    mask_h, mask_w = mask.shape
                    img_w, img_h = image.size
                    if mask_h != img_h or mask_w != img_w:
                        mask_img = Image.fromarray(mask * 255)
                        mask_img = mask_img.resize((img_w, img_h), Image.Resampling.NEAREST)
                        mask = np.array(mask_img)
                    masks.append(mask)
                except Exception as e:
                    logger.warning(f"Failed to decode mask for detection: {e}")

        if not masks:
            return image.copy()

        # Combine all masks
        combined_mask = self.combine_masks(masks)

        # Apply the masking effect
        return self.apply_mask(
            image=image,
            mask=combined_mask,
            strategy=strategy,
            fill_color=fill_color,
        )

    def extract_foreground(
        self,
        image: Image.Image,
        mask: np.ndarray,
        background_color: tuple[int, int, int] = (0, 0, 0),
    ) -> Image.Image:
        """Extract only the foreground (masked region) with a solid background.

        Useful for generating cleaner Re-ID embeddings by removing background
        distractions.

        Args:
            image: Source PIL Image
            mask: Binary mask where non-zero indicates foreground
            background_color: Color for the background (default black)

        Returns:
            Image with foreground preserved and background replaced
        """
        # Create background image
        background = Image.new("RGB", image.size, background_color)

        # Convert mask to PIL Image (foreground=white)
        binary_mask = ((mask > 0) * 255).astype(np.uint8)
        mask_image = Image.fromarray(binary_mask, mode="L")

        # Composite: use original where mask is white, background elsewhere
        return Image.composite(image, background, mask_image)

    def crop_masked_region(
        self,
        image: Image.Image,
        mask: np.ndarray,
        padding: int = 0,
    ) -> Image.Image:
        """Crop the image to the bounding box of the masked region.

        Useful for extracting just the detected entity for Re-ID embedding.

        Args:
            image: Source PIL Image
            mask: Binary mask where non-zero indicates the region of interest
            padding: Extra pixels to include around the mask bounds

        Returns:
            Cropped image containing the masked region
        """
        # Find bounding box of the mask
        rows = np.any(mask > 0, axis=1)
        cols = np.any(mask > 0, axis=0)

        if not np.any(rows) or not np.any(cols):
            # Empty mask, return empty image
            return Image.new("RGB", (1, 1), (0, 0, 0))

        y_min, y_max = np.where(rows)[0][[0, -1]]
        x_min, x_max = np.where(cols)[0][[0, -1]]

        # Apply padding (clamped to image bounds)
        img_w, img_h = image.size
        x_min = max(0, x_min - padding)
        y_min = max(0, y_min - padding)
        x_max = min(img_w - 1, x_max + padding)
        y_max = min(img_h - 1, y_max + padding)

        # Crop the image
        return image.crop((x_min, y_min, x_max + 1, y_max + 1))


# Global service instance
_privacy_masking_service: PrivacyMaskingService | None = None


def get_privacy_masking_service() -> PrivacyMaskingService:
    """Get or create the global PrivacyMaskingService instance.

    Returns:
        Global PrivacyMaskingService instance
    """
    global _privacy_masking_service  # noqa: PLW0603
    if _privacy_masking_service is None:
        _privacy_masking_service = PrivacyMaskingService()
    return _privacy_masking_service


def reset_privacy_masking_service() -> None:
    """Reset the global PrivacyMaskingService instance (for testing)."""
    global _privacy_masking_service  # noqa: PLW0603
    _privacy_masking_service = None
