"""Threat Detection Module for Weapon/Dangerous Object Detection.

This module provides the ThreatDetector class for detecting weapons and
threatening objects in security camera images using YOLOv8 object detection.

Note: YOLOv8/Ultralytics models have their own optimization through export
to TensorRT/ONNX. torch.compile() integration is limited for these models.
True batch inference is fully supported (NEM-3377).

Model: Weapon-Detection YOLOv8 variant from HuggingFace
VRAM: ~400MB
Priority: CRITICAL (should never be evicted if possible)

Classes detected: knife, gun, rifle, pistol, and other weapons

Reference: https://huggingface.co/Subh775/Threat-Detection-YOLOv8n
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import numpy as np
import torch
from PIL import Image

if TYPE_CHECKING:
    from numpy.typing import NDArray

# Add parent directory to path for shared utilities
_ai_dir = Path(__file__).parent.parent.parent
if str(_ai_dir) not in sys.path:
    sys.path.insert(0, str(_ai_dir))

from torch_optimizations import BatchConfig, BatchProcessor  # noqa: E402

logger = logging.getLogger(__name__)

# Severity levels for different threat types
# Critical: Firearms that can cause mass casualties
# High: Bladed weapons that can cause serious injury
# Medium: Blunt weapons or potential weapons
SeverityLevel = Literal["critical", "high", "medium"]

# Threat class mapping based on typical weapon detection model outputs
# Maps class ID to (threat_type, severity)
# Note: Actual class IDs may vary based on the specific model used.
# This mapping should be updated based on the model's classes.txt file.
THREAT_CLASSES: dict[int, tuple[str, SeverityLevel]] = {
    0: ("knife", "high"),
    1: ("gun", "critical"),
    2: ("rifle", "critical"),
    3: ("pistol", "critical"),
    4: ("bat", "medium"),
    5: ("crowbar", "medium"),
}

# Extended mapping for string-based class names (some models use string labels)
THREAT_CLASSES_BY_NAME: dict[str, SeverityLevel] = {
    "knife": "high",
    "gun": "critical",
    "rifle": "critical",
    "pistol": "critical",
    "firearm": "critical",
    "weapon": "high",
    "bat": "medium",
    "crowbar": "medium",
    "hammer": "medium",
    "sword": "high",
    "machete": "high",
    "axe": "high",
}

# Severity ordering for comparison (lower index = higher severity)
SEVERITY_ORDER: dict[str, int] = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "none": 3,
}


@dataclass
class ThreatDetection:
    """A single threat detection result.

    Attributes:
        threat_type: Type of threat detected (e.g., "knife", "gun", "rifle")
        confidence: Detection confidence score (0.0 to 1.0)
        bbox: Bounding box coordinates [x1, y1, x2, y2] in pixels
        severity: Severity level ("critical", "high", or "medium")
    """

    threat_type: str
    confidence: float
    bbox: list[float]
    severity: SeverityLevel

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "threat_type": self.threat_type,
            "confidence": round(self.confidence, 4),
            "bbox": [round(c, 2) for c in self.bbox],
            "severity": self.severity,
        }


@dataclass
class ThreatResult:
    """Result from threat detection analysis.

    Attributes:
        threats: List of individual threat detections
        has_threat: Whether any threat was detected
        max_severity: Highest severity level among all detections ("none" if no threats)
        inference_time_ms: Time taken for inference in milliseconds
    """

    threats: list[ThreatDetection] = field(default_factory=list)
    has_threat: bool = False
    max_severity: str = "none"
    inference_time_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "threats": [t.to_dict() for t in self.threats],
            "has_threat": self.has_threat,
            "max_severity": self.max_severity,
            "inference_time_ms": round(self.inference_time_ms, 2),
        }

    def to_context_string(self) -> str:
        """Generate human-readable context string for Nemotron."""
        if not self.has_threat:
            return "No weapons or threatening objects detected."

        lines = ["[THREAT DETECTED]"]
        for threat in self.threats:
            severity_marker = (
                "[CRITICAL]"
                if threat.severity == "critical"
                else "[HIGH]"
                if threat.severity == "high"
                else "[MEDIUM]"
            )
            lines.append(
                f"  - {severity_marker} {threat.threat_type.upper()}: "
                f"confidence={threat.confidence:.0%}"
            )

        lines.append(f"Maximum severity: {self.max_severity.upper()}")
        return "\n".join(lines)


class ThreatDetector:
    """YOLOv8 threat detection for weapons and dangerous objects.

    This class wraps a YOLOv8 model trained for weapon detection, providing
    an interface for detecting knives, guns, rifles, and other threatening
    objects in security camera images.

    Supports:
    - True batch inference with optimal batching (NEM-3377)

    Note: YOLOv8/Ultralytics models are optimized via TensorRT/ONNX export
    rather than torch.compile(). For maximum performance, export the model
    to TensorRT format.

    The model has CRITICAL priority and should be loaded quickly when needed.
    All detections are logged at WARNING level for security auditing.

    Attributes:
        model_path: Path to the YOLOv8 model weights
        device: Device to run inference on (e.g., "cuda:0", "cpu")
        confidence_threshold: Minimum confidence for detection (default: 0.5)
    """

    def __init__(
        self,
        model_path: str,
        device: str = "cuda:0",
        confidence_threshold: float = 0.5,
        max_batch_size: int = 8,
    ):
        """Initialize the threat detector.

        Args:
            model_path: Path to the YOLOv8 model weights file or directory
            device: Device to run inference on
            confidence_threshold: Minimum confidence threshold for detections
            max_batch_size: Maximum batch size for batch inference (NEM-3377).
        """
        self.model_path = model_path
        self.device = device
        self.confidence_threshold = confidence_threshold
        self.model: Any = None
        self._class_names: dict[int, str] = {}

        # Batch processing configuration (NEM-3377)
        self.batch_processor = BatchProcessor(BatchConfig(max_batch_size=max_batch_size))

        logger.info(f"Initializing ThreatDetector from {self.model_path}")

    def load_model(self) -> ThreatDetector:
        """Load the YOLOv8 model into memory.

        Returns:
            Self for method chaining.

        Raises:
            FileNotFoundError: If model weights are not found
            RuntimeError: If model loading fails
        """
        try:
            from ultralytics import YOLO
        except ImportError as e:
            logger.error("ultralytics package not installed. Install with: pip install ultralytics")
            raise ImportError("ultralytics package required for ThreatDetector") from e

        logger.info("Loading Threat Detection YOLOv8 model...")

        try:
            self.model = YOLO(self.model_path)

            # Move to appropriate device
            if "cuda" in self.device and torch.cuda.is_available():
                logger.info(f"ThreatDetector loaded on {self.device}")
            else:
                self.device = "cpu"
                logger.info("ThreatDetector using CPU (CUDA not available)")

            # Cache class names from model
            if hasattr(self.model, "names"):
                self._class_names = self.model.names
                logger.info(f"Model classes: {self._class_names}")

            logger.info("ThreatDetector loaded successfully")
            return self

        except Exception as e:
            logger.error(f"Failed to load ThreatDetector model: {e}")
            raise RuntimeError(f"Failed to load threat detection model: {e}") from e

    def unload(self) -> None:
        """Unload the model from memory and free resources."""
        if self.model is not None:
            del self.model
            self.model = None

            if torch.cuda.is_available():
                torch.cuda.empty_cache()

            logger.info("ThreatDetector model unloaded")

    def detect_threats(
        self,
        image: Image.Image | NDArray[np.uint8],
    ) -> ThreatResult:
        """Detect weapons and threatening objects in an image.

        Args:
            image: PIL Image or numpy array to analyze

        Returns:
            ThreatResult containing all detected threats and metadata

        Raises:
            RuntimeError: If model is not loaded
        """
        import time

        if self.model is None:
            raise RuntimeError("ThreatDetector model not loaded. Call load_model() first.")

        start_time = time.perf_counter()

        # Run inference
        results = self.model(image, verbose=False, device=self.device)

        threats: list[ThreatDetection] = []
        max_severity: str | None = None

        # Process results
        if results and len(results) > 0 and results[0].boxes is not None:
            boxes = results[0].boxes

            for box in boxes:
                conf = float(box.conf[0])
                cls_id = int(box.cls[0])

                # Skip low-confidence detections
                if conf < self.confidence_threshold:
                    continue

                # Determine threat type and severity
                if cls_id in THREAT_CLASSES:
                    threat_type, severity = THREAT_CLASSES[cls_id]
                elif cls_id in self._class_names:
                    class_name = self._class_names[cls_id].lower()
                    threat_type = class_name
                    severity = THREAT_CLASSES_BY_NAME.get(class_name, "medium")
                else:
                    threat_type = f"unknown_threat_{cls_id}"
                    severity = "medium"

                # Extract bounding box
                bbox = box.xyxy[0].tolist()

                # Create threat detection
                threat = ThreatDetection(
                    threat_type=threat_type,
                    confidence=conf,
                    bbox=bbox,
                    severity=severity,
                )
                threats.append(threat)

                # Track maximum severity
                if max_severity is None or SEVERITY_ORDER[severity] < SEVERITY_ORDER[max_severity]:
                    max_severity = severity

                # Log all threat detections at WARNING level for security auditing
                logger.warning(
                    f"THREAT DETECTED: {threat_type} "
                    f"(severity={severity}, confidence={conf:.2f}, bbox={bbox})"
                )

        inference_time_ms = (time.perf_counter() - start_time) * 1000

        return ThreatResult(
            threats=threats,
            has_threat=len(threats) > 0,
            max_severity=max_severity or "none",
            inference_time_ms=inference_time_ms,
        )

    def set_confidence_threshold(self, threshold: float) -> None:
        """Set the confidence threshold for detections.

        Args:
            threshold: New confidence threshold (0.0 to 1.0)

        Raises:
            ValueError: If threshold is not in valid range
        """
        if not 0.0 <= threshold <= 1.0:
            raise ValueError(f"Threshold must be between 0.0 and 1.0, got {threshold}")

        self.confidence_threshold = threshold
        logger.info(f"ThreatDetector confidence threshold set to {threshold}")

    def get_supported_classes(self) -> list[str]:
        """Get list of supported threat classes.

        Returns:
            List of class names the model can detect
        """
        if self.model is None:
            return list(THREAT_CLASSES_BY_NAME.keys())

        return list(self._class_names.values()) if self._class_names else []


def load_threat_detector(
    model_path: str,
    device: str = "cuda:0",
    confidence_threshold: float = 0.5,
) -> ThreatDetector:
    """Factory function for creating and loading a ThreatDetector.

    This function is designed for use with the model registry's on-demand
    loading system. It creates a ThreatDetector instance and loads the model
    in a single call.

    Args:
        model_path: Path to the YOLOv8 model weights
        device: Device to run inference on
        confidence_threshold: Minimum confidence for detections

    Returns:
        Loaded ThreatDetector instance ready for inference
    """
    detector = ThreatDetector(
        model_path=model_path,
        device=device,
        confidence_threshold=confidence_threshold,
    )
    return detector.load_model()
