"""HeatmapGenerator for generating movement heatmap visualizations.

This module provides the HeatmapGenerator class for real-time heatmap generation
using the supervision library's HeatMapAnnotator or a custom accumulator approach.

The generator tracks detection positions over time and can produce colored heatmap
images showing activity patterns across the camera's field of view.

Example:
    from ai.enrichment.heatmap_generator import HeatmapGenerator

    # Create generator
    generator = HeatmapGenerator(width=1920, height=1080)

    # Add detections from processing pipeline
    for detection in detections:
        generator.add_detection(detection.bbox_x, detection.bbox_y)

    # Generate heatmap image
    heatmap_image = generator.render()

    # Get as base64 for API response
    base64_data = generator.render_base64()
"""

from __future__ import annotations

import base64
import io
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    import supervision as sv

logger = logging.getLogger(__name__)

# Default settings
DEFAULT_DECAY_FACTOR = 0.99  # Decay factor for exponential moving average
DEFAULT_KERNEL_SIZE = 15  # Gaussian kernel size for smoothing


@dataclass
class HeatmapConfig:
    """Configuration for heatmap generation.

    Attributes:
        width: Frame width in pixels.
        height: Frame height in pixels.
        decay_factor: Exponential decay factor for temporal smoothing (0-1).
        kernel_size: Size of Gaussian smoothing kernel.
        colormap: Matplotlib colormap name for visualization.
        opacity: Opacity of the heatmap overlay (0-1).
        use_supervision: Whether to use supervision's HeatMapAnnotator.
    """

    width: int = 1920
    height: int = 1080
    decay_factor: float = DEFAULT_DECAY_FACTOR
    kernel_size: int = DEFAULT_KERNEL_SIZE
    colormap: str = "jet"
    opacity: float = 0.6
    use_supervision: bool = True


@dataclass
class DetectionPoint:
    """A single detection point with position and metadata.

    Attributes:
        x: X coordinate of the detection center.
        y: Y coordinate of the detection center.
        weight: Weight/importance of the detection (default 1.0).
        timestamp: When the detection occurred.
        object_type: Type of detected object (optional).
    """

    x: int
    y: int
    weight: float = 1.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    object_type: str | None = None


class HeatmapGenerator:
    """Generator for movement heatmap visualizations.

    This class maintains an accumulator of detection positions and can generate
    colored heatmap images showing activity patterns. It supports two modes:

    1. Supervision mode: Uses the supervision library's HeatMapAnnotator for
       efficient heatmap generation with built-in decay and smoothing.

    2. Custom mode: Uses a custom accumulator with numpy for environments
       where supervision is not available.

    Attributes:
        config: HeatmapConfig with generation settings.
        accumulator: 2D numpy array of detection counts.
        total_detections: Running count of detections added.

    Example:
        generator = HeatmapGenerator(width=1920, height=1080)

        # Process detections from a frame
        for detection in frame_detections:
            cx = detection.bbox_x + detection.bbox_width // 2
            cy = detection.bbox_y + detection.bbox_height // 2
            generator.add_detection(cx, cy)

        # Render heatmap as numpy array
        heatmap = generator.render()

        # Or get as base64-encoded PNG
        base64_data = generator.render_base64()
    """

    def __init__(
        self,
        width: int = 1920,
        height: int = 1080,
        decay_factor: float = DEFAULT_DECAY_FACTOR,
        kernel_size: int = DEFAULT_KERNEL_SIZE,
        colormap: str = "jet",
        opacity: float = 0.6,
        use_supervision: bool = True,
    ) -> None:
        """Initialize the heatmap generator.

        Args:
            width: Frame width in pixels.
            height: Frame height in pixels.
            decay_factor: Exponential decay factor for temporal smoothing.
            kernel_size: Size of Gaussian smoothing kernel.
            colormap: Matplotlib colormap name.
            opacity: Opacity of the heatmap overlay.
            use_supervision: Whether to use supervision's HeatMapAnnotator.
        """
        self.config = HeatmapConfig(
            width=width,
            height=height,
            decay_factor=decay_factor,
            kernel_size=kernel_size,
            colormap=colormap,
            opacity=opacity,
            use_supervision=use_supervision,
        )

        # Initialize accumulator
        self.accumulator = np.zeros((height, width), dtype=np.float32)
        self.total_detections = 0
        self.last_updated = datetime.now(UTC)

        # Supervision annotator (lazy initialized)
        self._sv_annotator: sv.HeatMapAnnotator | None = None
        self._sv: Any = None

    def _get_supervision(self) -> Any:
        """Lazily import supervision library.

        Returns:
            The supervision module.

        Raises:
            ImportError: If supervision is not installed.
        """
        if self._sv is None:
            try:
                import supervision as sv

                self._sv = sv
            except ImportError:
                logger.warning("supervision library not available, using custom heatmap generator")
                self.config.use_supervision = False
                return None
        return self._sv

    def _get_sv_annotator(self) -> sv.HeatMapAnnotator | None:
        """Get or create the supervision HeatMapAnnotator.

        Returns:
            HeatMapAnnotator instance, or None if supervision not available.
        """
        if self._sv_annotator is None:
            sv = self._get_supervision()
            if sv is None:
                return None

            self._sv_annotator = sv.HeatMapAnnotator(
                position=sv.Position.BOTTOM_CENTER,
                opacity=self.config.opacity,
                radius=self.config.kernel_size,
                kernel_size=self.config.kernel_size,
            )
        return self._sv_annotator

    def add_detection(
        self,
        x: int,
        y: int,
        weight: float = 1.0,
        object_type: str | None = None,
    ) -> None:
        """Add a detection point to the accumulator.

        Args:
            x: X coordinate of the detection center.
            y: Y coordinate of the detection center.
            weight: Weight/importance of the detection.
            object_type: Type of detected object (optional).
        """
        # Clamp coordinates to valid range
        x = max(0, min(x, self.config.width - 1))
        y = max(0, min(y, self.config.height - 1))

        # Add to accumulator with Gaussian spread
        self._add_gaussian(x, y, weight)

        self.total_detections += 1
        self.last_updated = datetime.now(UTC)

        logger.debug(
            f"Added detection at ({x}, {y})",
            extra={
                "x": x,
                "y": y,
                "weight": weight,
                "object_type": object_type,
                "total_detections": self.total_detections,
            },
        )

    def add_bbox_detection(
        self,
        bbox_x: int,
        bbox_y: int,
        bbox_width: int,
        bbox_height: int,
        weight: float = 1.0,
        object_type: str | None = None,
    ) -> None:
        """Add a detection from bounding box coordinates.

        Uses the center of the bounding box as the detection point.

        Args:
            bbox_x: X coordinate of the bounding box top-left corner.
            bbox_y: Y coordinate of the bounding box top-left corner.
            bbox_width: Width of the bounding box.
            bbox_height: Height of the bounding box.
            weight: Weight/importance of the detection.
            object_type: Type of detected object (optional).
        """
        # Calculate center of bounding box
        center_x = bbox_x + bbox_width // 2
        center_y = bbox_y + bbox_height // 2

        self.add_detection(center_x, center_y, weight, object_type)

    def _add_gaussian(self, x: int, y: int, weight: float) -> None:
        """Add a Gaussian blob to the accumulator at the given position.

        Args:
            x: X coordinate.
            y: Y coordinate.
            weight: Weight to apply.
        """
        # Create a Gaussian kernel centered at (x, y)
        kernel_size = self.config.kernel_size
        sigma = kernel_size / 4.0

        # Calculate bounds
        x_start = max(0, x - kernel_size)
        x_end = min(self.config.width, x + kernel_size + 1)
        y_start = max(0, y - kernel_size)
        y_end = min(self.config.height, y + kernel_size + 1)

        # Generate Gaussian values
        for yi in range(y_start, y_end):
            for xi in range(x_start, x_end):
                dist_sq = (xi - x) ** 2 + (yi - y) ** 2
                value = weight * np.exp(-dist_sq / (2 * sigma**2))
                self.accumulator[yi, xi] += value

    def apply_decay(self) -> None:
        """Apply temporal decay to the accumulator.

        This reduces the intensity of older detections, allowing the heatmap
        to reflect recent activity more strongly.
        """
        self.accumulator *= self.config.decay_factor

    def render(self, apply_colormap: bool = True) -> np.ndarray:
        """Render the current heatmap as a numpy array.

        Args:
            apply_colormap: If True, apply colormap to create RGB image.
                If False, return raw intensity values.

        Returns:
            Heatmap image as numpy array:
            - If apply_colormap=True: RGB uint8 array shape (H, W, 3)
            - If apply_colormap=False: float32 array shape (H, W)
        """
        if not apply_colormap:
            return self.accumulator.copy()

        return self._apply_colormap(self.accumulator)

    def _apply_colormap(self, intensity: np.ndarray) -> np.ndarray:
        """Apply colormap to intensity values.

        Args:
            intensity: 2D float array of intensity values.

        Returns:
            RGB uint8 array of shape (H, W, 3).
        """
        try:
            import matplotlib
            from matplotlib import cm

            matplotlib.use("Agg")
        except ImportError as e:
            logger.error(f"matplotlib not installed: {e}")
            # Fallback to grayscale
            normalized = intensity / (intensity.max() + 1e-8)
            grayscale = (normalized * 255).astype(np.uint8)
            return np.stack([grayscale, grayscale, grayscale], axis=-1)

        # Normalize to 0-1
        max_val = intensity.max()
        if max_val > 0:
            normalized = intensity / max_val
        else:
            normalized = intensity

        # Apply colormap
        cmap = cm.get_cmap(self.config.colormap)
        colored = cmap(normalized)

        # Convert to uint8 RGB (drop alpha channel)
        rgb = (colored[:, :, :3] * 255).astype(np.uint8)
        return rgb

    def render_rgba(self) -> np.ndarray:
        """Render the heatmap as an RGBA image with intensity-based alpha.

        Returns:
            RGBA uint8 array of shape (H, W, 4).
        """
        try:
            import matplotlib
            from matplotlib import cm

            matplotlib.use("Agg")
        except ImportError as e:
            logger.error(f"matplotlib not installed: {e}")
            raise ImportError("matplotlib required for RGBA rendering") from e

        # Normalize to 0-1
        max_val = self.accumulator.max()
        if max_val > 0:
            normalized = self.accumulator / max_val
        else:
            normalized = self.accumulator

        # Apply colormap
        cmap = cm.get_cmap(self.config.colormap)
        colored = cmap(normalized)

        # Set alpha based on intensity
        colored[:, :, 3] = normalized * self.config.opacity

        # Convert to uint8 RGBA
        rgba = (colored * 255).astype(np.uint8)
        return rgba

    def render_base64(self, format: str = "PNG") -> str:
        """Render the heatmap as a base64-encoded image.

        Args:
            format: Image format (PNG, JPEG, etc.).

        Returns:
            Base64-encoded image string.
        """
        try:
            from PIL import Image
        except ImportError as e:
            logger.error(f"PIL not installed: {e}")
            raise ImportError("PIL (Pillow) required for base64 rendering") from e

        # Render RGBA image
        rgba_array = self.render_rgba()

        # Create PIL image
        img = Image.fromarray(rgba_array, mode="RGBA")

        # Encode to base64
        buffer = io.BytesIO()
        img.save(buffer, format=format)
        buffer.seek(0)
        return base64.b64encode(buffer.read()).decode("utf-8")

    def render_overlay(
        self,
        background: np.ndarray,
    ) -> np.ndarray:
        """Render the heatmap overlaid on a background image.

        Args:
            background: Background image as numpy array (H, W, 3) or (H, W).

        Returns:
            Composite image as numpy array (H, W, 3).
        """
        # Ensure background is RGB
        if len(background.shape) == 2:
            background = np.stack([background, background, background], axis=-1)
        elif background.shape[2] == 4:
            background = background[:, :, :3]

        # Resize heatmap if dimensions don't match
        if background.shape[0] != self.config.height or background.shape[1] != self.config.width:
            try:
                from scipy.ndimage import zoom

                factors = (
                    background.shape[0] / self.config.height,
                    background.shape[1] / self.config.width,
                )
                resized_accumulator = zoom(self.accumulator, factors, order=1)
            except ImportError:
                logger.warning("scipy not available, returning background without overlay")
                return background
        else:
            resized_accumulator = self.accumulator

        # Render heatmap as RGBA
        config_backup = self.config.height, self.config.width
        self.config.height, self.config.width = background.shape[:2]

        # Temporarily use resized accumulator
        original_accumulator = self.accumulator
        self.accumulator = resized_accumulator

        rgba_heatmap = self.render_rgba()

        # Restore original
        self.accumulator = original_accumulator
        self.config.height, self.config.width = config_backup

        # Blend heatmap with background
        alpha = rgba_heatmap[:, :, 3:4] / 255.0
        rgb_heatmap = rgba_heatmap[:, :, :3]

        composite = (1 - alpha) * background + alpha * rgb_heatmap
        return composite.astype(np.uint8)

    def reset(self) -> None:
        """Reset the accumulator to zero."""
        self.accumulator.fill(0)
        self.total_detections = 0
        self.last_updated = datetime.now(UTC)
        logger.debug("Heatmap accumulator reset")

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about the current heatmap.

        Returns:
            Dictionary with heatmap statistics.
        """
        return {
            "width": self.config.width,
            "height": self.config.height,
            "total_detections": self.total_detections,
            "max_intensity": float(self.accumulator.max()),
            "mean_intensity": float(self.accumulator.mean()),
            "last_updated": self.last_updated.isoformat(),
            "decay_factor": self.config.decay_factor,
            "colormap": self.config.colormap,
        }

    def save(self, path: str, format: str = "PNG") -> None:
        """Save the heatmap to a file.

        Args:
            path: File path to save to.
            format: Image format (PNG, JPEG, etc.).
        """
        try:
            from PIL import Image
        except ImportError as e:
            logger.error(f"PIL not installed: {e}")
            raise ImportError("PIL (Pillow) required for saving") from e

        rgba_array = self.render_rgba()
        img = Image.fromarray(rgba_array, mode="RGBA")
        img.save(path, format=format)
        logger.info(f"Saved heatmap to {path}")

    @classmethod
    def from_detections(
        cls,
        detections: list[tuple[int, int]],
        width: int = 1920,
        height: int = 1080,
        **kwargs: Any,
    ) -> HeatmapGenerator:
        """Create a heatmap generator from a list of detection coordinates.

        Args:
            detections: List of (x, y) coordinate tuples.
            width: Frame width in pixels.
            height: Frame height in pixels.
            **kwargs: Additional arguments passed to __init__.

        Returns:
            HeatmapGenerator instance with detections added.
        """
        generator = cls(width=width, height=height, **kwargs)
        for x, y in detections:
            generator.add_detection(x, y)
        return generator

    @classmethod
    def from_supervision_detections(
        cls,
        detections: sv.Detections,
        width: int = 1920,
        height: int = 1080,
        **kwargs: Any,
    ) -> HeatmapGenerator:
        """Create a heatmap generator from supervision Detections.

        Args:
            detections: Supervision Detections object.
            width: Frame width in pixels.
            height: Frame height in pixels.
            **kwargs: Additional arguments passed to __init__.

        Returns:
            HeatmapGenerator instance with detections added.
        """
        generator = cls(width=width, height=height, **kwargs)

        # Extract bounding box centers from supervision Detections
        if detections.xyxy is not None and len(detections.xyxy) > 0:
            for box in detections.xyxy:
                x1, y1, x2, y2 = box
                center_x = int((x1 + x2) / 2)
                center_y = int((y1 + y2) / 2)
                generator.add_detection(center_x, center_y)

        return generator
