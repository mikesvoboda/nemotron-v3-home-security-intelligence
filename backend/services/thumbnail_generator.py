"""Thumbnail generator service for creating detection previews with bounding boxes.

This service generates thumbnail images from detection results, overlaying
bounding boxes with labels to visualize detected objects. Thumbnails are
used for quick preview in the dashboard UI.

Features:
    - Load and resize images to thumbnail size (default: 320x240)
    - Draw colored bounding boxes based on object type
    - Add text labels with object type and confidence score
    - Maintain aspect ratio with padding
    - Save as optimized JPEG files

Color Scheme (by object type):
    - person: red (#E74856)
    - car/truck: blue (#3B82F6)
    - dog/cat: green (#76B900)
    - bicycle/motorcycle: yellow (#FFB800)
    - bird: purple (#A855F7)
    - default: white (#FFFFFF)

Output Format:
    - File: {output_dir}/{detection_id}_thumb.jpg
    - Quality: 85
    - Format: JPEG
"""

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from backend.core.logging import get_logger, sanitize_error

# Keep sanitize_error imported for future use, suppress unused import warning
_ = sanitize_error

logger = get_logger(__name__)


# Color mapping for object types (RGB tuples)
OBJECT_COLORS = {
    "person": (231, 72, 86),  # red
    "car": (59, 130, 246),  # blue
    "truck": (59, 130, 246),  # blue
    "dog": (118, 185, 0),  # green
    "cat": (118, 185, 0),  # green
    "bicycle": (255, 184, 0),  # yellow
    "motorcycle": (255, 184, 0),  # yellow
    "bird": (168, 85, 247),  # purple
}

DEFAULT_COLOR = (255, 255, 255)  # white


class ThumbnailGenerator:
    """Generates thumbnail images with bounding boxes for detections.

    This service creates visual previews of detections by:
    1. Loading the original detection image
    2. Drawing bounding boxes with labels
    3. Resizing to thumbnail size
    4. Saving as optimized JPEG

    Thumbnails are used in the dashboard UI for quick preview of detections.
    """

    def __init__(self, output_dir: str = "data/thumbnails"):
        """Initialize thumbnail generator with output directory.

        Args:
            output_dir: Directory to save thumbnails to. Relative paths are
                       relative to backend/. Defaults to "data/thumbnails".
        """
        self.output_dir = Path(output_dir)
        self._ensure_output_dir()

    def _ensure_output_dir(self) -> None:
        """Create output directory if it doesn't exist."""
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Thumbnail output directory ready: {self.output_dir}")
        except Exception as e:
            logger.error(
                f"Failed to create thumbnail output directory {self.output_dir}: {e}", exc_info=True
            )
            raise

    def generate_thumbnail(
        self,
        image_path: str,
        detections: list[dict[str, Any]],
        output_size: tuple[int, int] = (320, 240),
        detection_id: int | str | None = None,
    ) -> str | None:
        """Generate thumbnail with bounding boxes from detection image.

        Loads the original image, draws bounding boxes for all detections,
        resizes to thumbnail size (maintaining aspect ratio with padding),
        and saves as JPEG.

        Args:
            image_path: Path to original detection image
            detections: List of detection dicts with bbox coordinates and metadata
            output_size: Thumbnail size as (width, height). Defaults to 320x240
            detection_id: Detection ID for output filename. If None, uses image filename

        Returns:
            Path to saved thumbnail file, or None if generation failed

        Detection dict format:
            {
                "object_type": "person",
                "confidence": 0.95,
                "bbox_x": 100,
                "bbox_y": 150,
                "bbox_width": 200,
                "bbox_height": 400
            }
        """
        try:
            # Load original image
            image: Image.Image = Image.open(image_path)  # type: ignore[assignment]
            if image.mode != "RGB":
                image = image.convert("RGB")

            # Draw bounding boxes
            image_with_boxes = self.draw_bounding_boxes(image, detections)

            # Resize to thumbnail size (maintain aspect ratio)
            thumbnail = self._resize_with_padding(image_with_boxes, output_size)

            # Generate output filename
            if detection_id is None:
                detection_id = Path(image_path).stem

            output_filename = f"{detection_id}_thumb.jpg"
            output_path = self.output_dir / output_filename

            # Save as JPEG with quality 85
            thumbnail.save(output_path, "JPEG", quality=85, optimize=True)

            logger.debug(f"Generated thumbnail: {output_path}")
            return str(output_path)

        except FileNotFoundError:
            logger.error(f"Image file not found: {image_path}")
            return None
        except PermissionError:
            logger.error(f"Permission denied saving thumbnail: {output_path}")
            return None
        except Exception as e:
            logger.error(f"Failed to generate thumbnail from {image_path}: {e}", exc_info=True)
            return None

    def draw_bounding_boxes(
        self,
        image: Image.Image,
        detections: list[dict[str, Any]],
    ) -> Image.Image:
        """Draw bounding boxes with labels on image.

        Draws colored rectangles around detected objects and adds text labels
        with object type and confidence score.

        Args:
            image: PIL Image to draw on
            detections: List of detection dicts with bbox and metadata

        Returns:
            New image with bounding boxes drawn
        """
        # Create a copy to avoid modifying original
        img_copy = image.copy()
        draw = ImageDraw.Draw(img_copy)

        # Try to load a font, fall back to default if unavailable
        font: Any
        try:
            # Try to use a TrueType font at size 14
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
        except Exception:
            try:
                # Try alternative font path
                font = ImageFont.truetype("/usr/share/fonts/dejavu/DejaVuSans.ttf", 14)
            except Exception:
                # Fall back to default PIL font
                font = ImageFont.load_default()
                logger.debug("Using default PIL font for thumbnail labels")

        for detection in detections:
            # Extract detection data
            object_type = detection.get("object_type", "unknown")
            confidence = detection.get("confidence", 0.0)
            bbox_x = detection.get("bbox_x")
            bbox_y = detection.get("bbox_y")
            bbox_width = detection.get("bbox_width")
            bbox_height = detection.get("bbox_height")

            # Skip if bbox coordinates are missing
            if any(v is None for v in [bbox_x, bbox_y, bbox_width, bbox_height]):
                logger.warning(f"Skipping detection with incomplete bbox: {detection}")
                continue

            # Calculate bounding box coordinates
            # Add None checks before arithmetic operations
            if bbox_width is None or bbox_height is None:
                logger.warning(f"Skipping detection with None in bbox dimensions: {detection}")
                continue

            x1, y1 = bbox_x, bbox_y
            x2, y2 = bbox_x + bbox_width, bbox_y + bbox_height

            # Get color for object type
            color = OBJECT_COLORS.get(object_type.lower(), DEFAULT_COLOR)

            # Draw rectangle (3px line width)
            draw.rectangle(
                [(x1, y1), (x2, y2)],
                outline=color,
                width=3,
            )

            # Draw label background and text
            label = f"{object_type} {confidence:.2f}"

            # Get text bounding box for background - need to check y1 is not None
            if y1 is None or x1 is None:
                logger.warning(f"Skipping label for detection with None coordinate: {detection}")
                continue

            label_y = y1 - 18
            # x1 and label_y are guaranteed to be non-None at this point
            bbox = draw.textbbox((x1, label_y), label, font=font)  # type: ignore[arg-type]

            # Draw label background (semi-transparent effect with filled rectangle)
            draw.rectangle(bbox, fill=color)

            # Draw text in white
            draw.text((x1, label_y), label, fill=(255, 255, 255), font=font)  # type: ignore[arg-type]

        return img_copy

    def _resize_with_padding(
        self,
        image: Image.Image,
        target_size: tuple[int, int],
    ) -> Image.Image:
        """Resize image to target size, maintaining aspect ratio with padding.

        Args:
            image: PIL Image to resize
            target_size: Target size as (width, height)

        Returns:
            Resized image with padding
        """
        target_width, target_height = target_size
        original_width, original_height = image.size

        # Calculate scaling factor to fit within target size
        scale = min(target_width / original_width, target_height / original_height)

        # Calculate new dimensions
        new_width = int(original_width * scale)
        new_height = int(original_height * scale)

        # Resize image
        resized = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # Create new image with padding (black background)
        padded = Image.new("RGB", target_size, (0, 0, 0))

        # Calculate position to paste (center)
        paste_x = (target_width - new_width) // 2
        paste_y = (target_height - new_height) // 2

        # Paste resized image onto padded background
        padded.paste(resized, (paste_x, paste_y))

        return padded

    def get_output_path(self, detection_id: int | str) -> Path:
        """Get output path for a detection thumbnail.

        Args:
            detection_id: Detection ID

        Returns:
            Path object for thumbnail file
        """
        return self.output_dir / f"{detection_id}_thumb.jpg"

    def delete_thumbnail(self, detection_id: int | str) -> bool:
        """Delete a thumbnail file.

        Args:
            detection_id: Detection ID

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            thumbnail_path = self.get_output_path(detection_id)
            if thumbnail_path.exists():
                thumbnail_path.unlink()
                logger.debug(f"Deleted thumbnail: {thumbnail_path}")
                return True
            else:
                logger.warning(f"Thumbnail not found: {thumbnail_path}")
                return False
        except Exception as e:
            logger.error(f"Failed to delete thumbnail for {detection_id}: {e}", exc_info=True)
            return False
