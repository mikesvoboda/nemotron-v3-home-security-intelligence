"""Depth Anything V2 model loader for monocular depth estimation.

This module provides async loading of Depth Anything V2 Small model and helper
functions for extracting depth information at specific locations.

The Depth Anything V2 model generates relative depth maps from single images,
which can be used to estimate how close detected objects are to the camera.
This information enhances Nemotron's risk analysis by providing spatial context.

Model details:
- HuggingFace: depth-anything/Depth-Anything-V2-Small-hf
- VRAM: ~100-200MB (very lightweight)
- Parameters: 24.8M
- License: Apache 2.0
- Output: Depth map with relative distance from camera

Depth values:
- Lower values (closer to 0) = objects closer to camera
- Higher values (closer to 1) = objects farther from camera
- Values are normalized to 0-1 range for Nemotron context
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import numpy as np

from backend.core.logging import get_logger

if TYPE_CHECKING:
    from numpy.typing import NDArray

logger = get_logger(__name__)


async def load_depth_model(model_path: str) -> Any:
    """Load Depth Anything V2 model from HuggingFace.

    This function loads the Depth Anything V2 Small model using the
    transformers depth-estimation pipeline.

    Args:
        model_path: HuggingFace model path (e.g., "depth-anything/Depth-Anything-V2-Small-hf")

    Returns:
        Transformers pipeline for depth estimation

    Raises:
        ImportError: If transformers or torch is not installed
        RuntimeError: If model loading fails
    """
    try:
        import torch
        from transformers import pipeline

        logger.info(f"Loading Depth Anything V2 model from {model_path}")

        loop = asyncio.get_event_loop()

        def _load_pipeline() -> Any:
            """Load depth estimation pipeline synchronously."""
            # Determine device
            if torch.cuda.is_available():
                device = 0  # Use first CUDA device
                logger.info("Depth Anything V2 will use CUDA")
            else:
                device = -1  # CPU
                logger.info("Depth Anything V2 will use CPU")

            # Create depth estimation pipeline
            depth_pipe = pipeline(
                task="depth-estimation",
                model=model_path,
                device=device,
            )

            return depth_pipe

        depth_pipe = await loop.run_in_executor(None, _load_pipeline)

        logger.info(f"Successfully loaded Depth Anything V2 model from {model_path}")
        return depth_pipe

    except ImportError as e:
        logger.warning(
            "transformers or torch package not installed. "
            "Install with: pip install transformers torch"
        )
        raise ImportError(
            "Depth Anything V2 requires transformers and torch. "
            "Install with: pip install transformers torch"
        ) from e

    except Exception as e:
        logger.error(
            "Failed to load Depth Anything V2 model",
            exc_info=True,
            extra={"model_path": model_path},
        )
        raise RuntimeError(f"Failed to load Depth Anything V2 model: {e}") from e


def normalize_depth_map(depth_output: Any) -> NDArray[np.float32]:
    """Normalize depth map output to 0-1 range.

    The depth estimation pipeline returns depth values that may have different
    ranges depending on the scene. This function normalizes them to a consistent
    0-1 range where:
    - 0 = closest to camera
    - 1 = farthest from camera

    Args:
        depth_output: Output from the depth estimation pipeline
            (typically a dict with 'depth' key or PIL Image)

    Returns:
        Normalized depth map as numpy array with values in [0, 1]
    """
    # Handle pipeline output format
    if hasattr(depth_output, "get"):
        # Dict-like output with 'depth' key
        depth_data = depth_output.get("depth", depth_output)
    else:
        depth_data = depth_output

    # Convert PIL Image to numpy if needed
    if hasattr(depth_data, "convert"):
        # It's a PIL Image
        depth_array = np.array(depth_data, dtype=np.float32)
    elif isinstance(depth_data, np.ndarray):
        depth_array = depth_data.astype(np.float32)
    else:
        # Try to convert to numpy array
        depth_array = np.array(depth_data, dtype=np.float32)

    # Normalize to 0-1 range
    min_val = depth_array.min()
    max_val = depth_array.max()

    if max_val - min_val > 0:
        normalized: NDArray[np.float32] = (depth_array - min_val) / (max_val - min_val)
    else:
        # Uniform depth (shouldn't happen in practice)
        normalized = np.zeros_like(depth_array)

    return normalized


def get_depth_at_bbox(
    depth_map: NDArray[np.float32],
    bbox: tuple[float, float, float, float],
    method: str = "center",
) -> float:
    """Extract depth value at a bounding box location.

    Args:
        depth_map: Normalized depth map (H x W) with values in [0, 1]
        bbox: Bounding box coordinates (x1, y1, x2, y2)
        method: How to sample depth:
            - "center": Sample at bbox center point (fastest)
            - "mean": Average depth over entire bbox (most accurate)
            - "median": Median depth over bbox (robust to outliers)
            - "min": Minimum depth in bbox (closest point)

    Returns:
        Relative depth value in [0, 1] where:
            - 0 = closest to camera
            - 1 = farthest from camera

    Raises:
        ValueError: If method is unknown or bbox is invalid
    """
    x1, y1, x2, y2 = bbox
    h, w = depth_map.shape[:2]

    # Clamp bbox to image boundaries
    x1 = max(0, min(int(x1), w - 1))
    y1 = max(0, min(int(y1), h - 1))
    x2 = max(0, min(int(x2), w - 1))
    y2 = max(0, min(int(y2), h - 1))

    # Ensure valid bbox
    if x2 <= x1 or y2 <= y1:
        # Invalid bbox, return middle depth
        return 0.5

    if method == "center":
        center_x = (x1 + x2) // 2
        center_y = (y1 + y2) // 2
        return float(depth_map[center_y, center_x])

    elif method == "mean":
        region = depth_map[y1:y2, x1:x2]
        return float(np.mean(region))

    elif method == "median":
        region = depth_map[y1:y2, x1:x2]
        return float(np.median(region))

    elif method == "min":
        region = depth_map[y1:y2, x1:x2]
        return float(np.min(region))

    else:
        raise ValueError(f"Unknown depth sampling method: {method}")


def get_depth_at_point(
    depth_map: NDArray[np.float32],
    x: int,
    y: int,
) -> float:
    """Extract depth value at a specific point.

    Args:
        depth_map: Normalized depth map (H x W) with values in [0, 1]
        x: X coordinate (column)
        y: Y coordinate (row)

    Returns:
        Relative depth value in [0, 1]
    """
    h, w = depth_map.shape[:2]

    # Clamp to image boundaries
    x = max(0, min(x, w - 1))
    y = max(0, min(y, h - 1))

    return float(depth_map[y, x])


def estimate_relative_distances(
    depth_map: NDArray[np.float32],
    bboxes: list[tuple[float, float, float, float]],
    method: str = "center",
) -> list[float]:
    """Estimate relative distances for multiple detections.

    Args:
        depth_map: Normalized depth map (H x W) with values in [0, 1]
        bboxes: List of bounding boxes (x1, y1, x2, y2)
        method: Depth sampling method (see get_depth_at_bbox)

    Returns:
        List of relative depth values, one per bbox
    """
    return [get_depth_at_bbox(depth_map, bbox, method) for bbox in bboxes]


def depth_to_proximity_label(depth_value: float) -> str:
    """Convert normalized depth value to human-readable proximity label.

    This is useful for Nemotron context to describe how close objects are.

    Args:
        depth_value: Normalized depth in [0, 1]

    Returns:
        Human-readable proximity label
    """
    if depth_value < 0.15:
        return "very close"
    elif depth_value < 0.35:
        return "close"
    elif depth_value < 0.55:
        return "moderate distance"
    elif depth_value < 0.75:
        return "far"
    else:
        return "very far"


def format_depth_for_nemotron(
    detections: list[dict[str, Any]],
    depth_values: list[float],
) -> str:
    """Format depth information for Nemotron context.

    Creates a human-readable description of object depths that can be
    appended to Nemotron's input context for risk analysis.

    Args:
        detections: List of detection dictionaries with 'class_name' key
        depth_values: Corresponding depth values for each detection

    Returns:
        Formatted string describing object proximities

    Example output:
        "Spatial context: person is very close to camera (depth: 0.12),
         car is at moderate distance (depth: 0.48)"
    """
    if not detections or not depth_values:
        return "No spatial depth information available."

    if len(detections) != len(depth_values):
        logger.warning(
            f"Detection count ({len(detections)}) doesn't match "
            f"depth value count ({len(depth_values)})"
        )
        # Use minimum length
        count = min(len(detections), len(depth_values))
        detections = detections[:count]
        depth_values = depth_values[:count]

    descriptions = []
    for det, depth in zip(detections, depth_values, strict=False):
        class_name = det.get("class_name", det.get("label", "object"))
        proximity = depth_to_proximity_label(depth)
        descriptions.append(f"{class_name} is {proximity} (depth: {depth:.2f})")

    return "Spatial context: " + ", ".join(descriptions)


def rank_detections_by_proximity(
    detections: list[dict[str, Any]],
    depth_values: list[float],
) -> list[tuple[dict[str, Any], float, int]]:
    """Rank detections by proximity to camera (closest first).

    Useful for prioritizing which detections are most relevant for
    security analysis (closer objects are often more important).

    Args:
        detections: List of detection dictionaries
        depth_values: Corresponding depth values

    Returns:
        List of tuples (detection, depth_value, original_index) sorted by
        proximity (closest first)
    """
    if len(detections) != len(depth_values):
        raise ValueError("Detection and depth value counts must match")

    # Create list of (detection, depth, original_index)
    indexed = [
        (det, depth, i) for i, (det, depth) in enumerate(zip(detections, depth_values, strict=True))
    ]

    # Sort by depth (lower = closer = higher priority)
    return sorted(indexed, key=lambda x: x[1])
