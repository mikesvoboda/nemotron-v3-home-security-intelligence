"""FastALPR loader for end-to-end license plate recognition (NEM-5569).

Replaces the two-step YOLO11-license-plate (300MB) + PaddleOCR (100MB) pipeline
with FastALPR's unified detection + OCR (~28MB total). Uses ONNX-optimized models
for fast inference: yolo-v9-t-384-license-plate-end2end + cct-xs-v1-global-model.

FastALPR provides:
- License plate detection (YOLOv9-tiny, end-to-end)
- OCR text recognition (CCT-XS, global model)
- MIT license, Python 3.10+
- Native ONNX Runtime inference

Usage:
    alpr = await load_fast_alpr()
    results = await run_fast_alpr(alpr, image)
    for plate in results:
        print(f"Plate: {plate.text} (confidence: {plate.confidence})")
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from backend.core.logging import get_logger

logger = get_logger(__name__)

# Default FastALPR models (smallest available, ONNX-native)
DEFAULT_DETECTOR_MODEL = "yolo-v9-t-384-license-plate-end2end"
DEFAULT_OCR_MODEL = "cct-xs-v1-global-model"


@dataclass(slots=True)
class FastALPRResult:
    """Result from FastALPR end-to-end plate recognition.

    Attributes:
        text: Cleaned plate text (uppercase, alphanumeric)
        confidence: OCR confidence score (0.0 to 1.0)
        bbox: Plate bounding box in original image coordinates (x1, y1, x2, y2)
        detection_confidence: Plate detection confidence
    """

    text: str
    confidence: float
    bbox: tuple[float, float, float, float]
    detection_confidence: float = 0.0


def _is_fast_alpr_available() -> bool:
    """Check if fast-alpr package is installed.

    Returns:
        True if fast_alpr is importable, False otherwise
    """
    try:
        import importlib.util

        return importlib.util.find_spec("fast_alpr") is not None
    except (ImportError, ModuleNotFoundError):
        return False


async def load_fast_alpr(model_path: str = "") -> Any:  # noqa: ARG001
    """Load FastALPR with default detection + OCR models.

    The model_path parameter is accepted for compatibility with the ModelManager
    interface but is not used — FastALPR downloads its own ONNX models on first use.

    Args:
        model_path: Unused, kept for ModelManager compatibility.

    Returns:
        Initialized ALPR instance.

    Raises:
        RuntimeError: If fast-alpr is not installed.
    """
    if not _is_fast_alpr_available():
        logger.info(
            "fast-alpr package not installed — FastALPR features disabled. "
            "Install with: pip install fast-alpr[onnx-gpu]"
        )
        raise RuntimeError(
            "fast-alpr package not installed. Install with: pip install fast-alpr[onnx-gpu]"
        )

    try:
        from fast_alpr import ALPR

        logger.info(
            f"Loading FastALPR (detector={DEFAULT_DETECTOR_MODEL}, ocr={DEFAULT_OCR_MODEL})"
        )

        loop = asyncio.get_running_loop()

        def _load() -> Any:
            return ALPR(
                detector_model=DEFAULT_DETECTOR_MODEL,
                ocr_model=DEFAULT_OCR_MODEL,
            )

        alpr = await loop.run_in_executor(None, _load)
        logger.info("FastALPR loaded successfully")
        return alpr

    except ImportError as e:
        logger.info(
            "fast-alpr package not installed — FastALPR features disabled. "
            "Install with: pip install fast-alpr[onnx-gpu]"
        )
        raise RuntimeError(
            "fast-alpr package not installed. Install with: pip install fast-alpr[onnx-gpu]"
        ) from e
    except Exception as e:
        logger.error("Failed to load FastALPR", exc_info=True)
        raise RuntimeError(f"Failed to load FastALPR: {e}") from e


async def run_fast_alpr(
    alpr: Any,
    image: Any,
    min_confidence: float = 0.3,
) -> list[FastALPRResult]:
    """Run end-to-end plate recognition on an image.

    Detects all license plates in the image and reads their text in one pass.

    Args:
        alpr: Initialized ALPR instance from load_fast_alpr().
        image: Input image — PIL Image, numpy array, or file path string.
        min_confidence: Minimum OCR confidence to include a result.

    Returns:
        List of FastALPRResult objects for detected plates.
    """
    import re

    import numpy as np
    from PIL import Image as PILImage

    loop = asyncio.get_running_loop()

    # Convert PIL Image to numpy array if needed (FastALPR accepts both)
    image_input: np.ndarray | str
    if isinstance(image, PILImage.Image):
        image_input = np.array(image.convert("RGB"))
    elif isinstance(image, str):
        image_input = image  # FastALPR accepts file paths directly
    else:
        image_input = image  # Assume numpy array

    def _predict() -> list[Any]:
        result: list[Any] = alpr.predict(image_input)
        return result

    try:
        raw_results = await loop.run_in_executor(None, _predict)
    except Exception as e:
        logger.warning(f"FastALPR prediction failed: {e}")
        return []

    results: list[FastALPRResult] = []
    plate_text_pattern = re.compile(r"[^A-Z0-9]")

    for result in raw_results:
        try:
            # FastALPR returns ALPRResult objects with detection and ocr attributes
            if not result.ocr or not result.ocr.text:
                continue

            ocr_conf = result.ocr.confidence if result.ocr.confidence else 0.0
            if ocr_conf < min_confidence:
                continue

            # Clean plate text
            raw_text = result.ocr.text
            cleaned = plate_text_pattern.sub("", raw_text.upper().strip())
            if len(cleaned) < 2:
                continue

            # Extract bounding box from detection
            det = result.detection
            bbox = (
                float(det.bounding_box.x1),
                float(det.bounding_box.y1),
                float(det.bounding_box.x2),
                float(det.bounding_box.y2),
            )
            det_conf = float(det.confidence) if det.confidence else 0.0

            results.append(
                FastALPRResult(
                    text=cleaned,
                    confidence=ocr_conf,
                    bbox=bbox,
                    detection_confidence=det_conf,
                )
            )

            logger.debug(f"FastALPR: plate '{cleaned}' (det={det_conf:.2f}, ocr={ocr_conf:.2f})")

        except Exception as e:
            logger.warning(f"Failed to parse FastALPR result: {e}")
            continue

    logger.info(f"FastALPR: detected {len(results)} plates")
    return results
