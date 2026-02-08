"""Shared utility functions for the AI Gateway.

Provides image decoding, preprocessing, normalization, and encoding
helpers used across all adapter modules.
"""

from __future__ import annotations

import base64
import io
import math

import numpy as np
from PIL import Image


def decode_base64_image(b64: str) -> np.ndarray:
    """Decode a base64-encoded image to a numpy array.

    Args:
        b64: Base64-encoded image string (JPEG, PNG, etc.).

    Returns:
        Numpy array with shape (H, W, 3) and dtype uint8 in RGB order.

    Raises:
        ValueError: If the base64 string is invalid or cannot be decoded
            as an image.
    """
    try:
        image_bytes = base64.b64decode(b64)
    except Exception as e:
        raise ValueError(f"Invalid base64 encoding: {e}") from e

    try:
        image = Image.open(io.BytesIO(image_bytes))
    except Exception as e:
        raise ValueError(f"Cannot decode image from bytes: {e}") from e

    if image.mode != "RGB":
        image = image.convert("RGB")

    return np.array(image, dtype=np.uint8)


def decode_base64_to_pil(b64: str) -> Image.Image:
    """Decode a base64-encoded image to a PIL Image.

    Args:
        b64: Base64-encoded image string.

    Returns:
        PIL Image in RGB mode.

    Raises:
        ValueError: If decoding fails.
    """
    try:
        image_bytes = base64.b64decode(b64)
    except Exception as e:
        raise ValueError(f"Invalid base64 encoding: {e}") from e

    try:
        image = Image.open(io.BytesIO(image_bytes))
    except Exception as e:
        raise ValueError(f"Cannot decode image from bytes: {e}") from e

    if image.mode != "RGB":
        image = image.convert("RGB")

    return image


def decode_base64_to_bytes(b64: str) -> bytes:
    """Decode a base64-encoded string to raw bytes.

    Args:
        b64: Base64-encoded string.

    Returns:
        Raw bytes.
    """
    return base64.b64decode(b64)


def encode_image_bytes(image: Image.Image, fmt: str = "PNG") -> str:
    """Encode a PIL Image to a base64 string.

    Args:
        image: PIL Image to encode.
        fmt: Image format (PNG, JPEG, etc.).

    Returns:
        Base64-encoded string of the image.
    """
    buffer = io.BytesIO()
    image.save(buffer, format=fmt)
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode("utf-8")


def preprocess_clip(image: np.ndarray) -> np.ndarray:
    """Preprocess an image for CLIP ViT-L ONNX Runtime inference.

    Resizes to 224x224, normalizes with ImageNet stats, and converts
    to NCHW FP32 format expected by the ONNX Runtime backend.

    Args:
        image: Numpy array (H, W, 3) uint8 in RGB order.

    Returns:
        Numpy array (1, 3, 224, 224) FP32 normalized.
    """
    # Resize to 224x224
    pil_img = Image.fromarray(image)
    pil_img = pil_img.resize((224, 224), Image.BILINEAR)
    arr = np.array(pil_img, dtype=np.float32) / 255.0

    # Normalize with CLIP/ImageNet statistics
    mean = np.array([0.48145466, 0.4578275, 0.40821073], dtype=np.float32)
    std = np.array([0.26862954, 0.26130258, 0.27577711], dtype=np.float32)
    arr = (arr - mean) / std

    # HWC -> CHW -> NCHW
    arr = arr.transpose(2, 0, 1)
    arr = np.expand_dims(arr, axis=0)

    return arr.astype(np.float32)


def preprocess_yolo(image_bytes: bytes, target_size: int = 640) -> np.ndarray:
    """Preprocess raw image bytes for YOLO TensorRT inference.

    Applies letterbox resizing to maintain aspect ratio, padding with
    gray (114, 114, 114) to reach target_size x target_size.

    Args:
        image_bytes: Raw image file bytes (JPEG, PNG, etc.).
        target_size: Target square dimension (default 640).

    Returns:
        Numpy array (1, 3, target_size, target_size) FP32 normalized [0, 1].
    """
    image = Image.open(io.BytesIO(image_bytes))
    if image.mode != "RGB":
        image = image.convert("RGB")

    orig_w, orig_h = image.size

    # Compute letterbox scale
    scale = min(target_size / orig_w, target_size / orig_h)
    new_w = int(orig_w * scale)
    new_h = int(orig_h * scale)

    # Resize maintaining aspect ratio
    resized = image.resize((new_w, new_h), Image.BILINEAR)

    # Create padded canvas with gray fill
    canvas = Image.new("RGB", (target_size, target_size), (114, 114, 114))
    pad_x = (target_size - new_w) // 2
    pad_y = (target_size - new_h) // 2
    canvas.paste(resized, (pad_x, pad_y))

    # Convert to float32 [0, 1] and NCHW
    arr = np.array(canvas, dtype=np.float32) / 255.0
    arr = arr.transpose(2, 0, 1)
    arr = np.expand_dims(arr, axis=0)

    return arr


def l2_normalize(embedding: list[float]) -> list[float]:
    """L2-normalize an embedding vector.

    Args:
        embedding: List of float values.

    Returns:
        L2-normalized embedding as a list of floats.
    """
    norm = math.sqrt(sum(x * x for x in embedding))
    if norm < 1e-12:
        return embedding
    return [x / norm for x in embedding]


def letterbox_scale_factors(
    orig_w: int, orig_h: int, target_size: int = 640
) -> tuple[float, int, int]:
    """Compute letterbox scaling parameters for YOLO post-processing.

    Used to reverse letterbox transforms on bounding box coordinates.

    Args:
        orig_w: Original image width.
        orig_h: Original image height.
        target_size: Target square dimension.

    Returns:
        Tuple of (scale, pad_x, pad_y).
    """
    scale = min(target_size / orig_w, target_size / orig_h)
    new_w = int(orig_w * scale)
    new_h = int(orig_h * scale)
    pad_x = (target_size - new_w) // 2
    pad_y = (target_size - new_h) // 2
    return scale, pad_x, pad_y
