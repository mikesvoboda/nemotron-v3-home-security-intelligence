"""YOLOv8n-pose Human Pose Estimation Module.

This module provides the PoseEstimator class for detecting body poses and
identifying suspicious postures using the YOLOv8n-pose model from Ultralytics.

Supports true batch inference for vision models (NEM-3377).

TensorRT Support (NEM-3838):
- Set POSE_USE_TENSORRT=true to enable TensorRT acceleration (2-3x speedup)
- TensorRT engine is auto-exported on first run if not found
- Engine files are GPU-architecture specific (.engine files)
- Falls back to PyTorch if TensorRT is unavailable

Features:
- Detects 17 COCO keypoints (nose, eyes, ears, shoulders, elbows, wrists, hips,
  knees, ankles)
- Classifies body posture (standing, crouching, running, reaching_up, etc.)
- Flags suspicious poses that may indicate concerning behavior (crouching, crawling,
  hiding)

Model Details:
- Model: ultralytics/yolov8n-pose
- VRAM: ~300MB (PyTorch), ~200MB (TensorRT FP16)
- Output: 17 keypoints per person (COCO format)

Environment Variables:
- POSE_USE_TENSORRT: Enable TensorRT acceleration (default: false)
- POSE_TENSORRT_ENGINE_PATH: Custom path for TensorRT engine file (optional)
- POSE_TENSORRT_FP16: Use FP16 precision for TensorRT (default: true)

Reference: https://docs.ultralytics.com/tasks/pose/
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch
from numpy.typing import NDArray
from PIL import Image

# Add parent directory to path for shared utilities
_ai_dir = Path(__file__).parent.parent.parent
if str(_ai_dir) not in sys.path:
    sys.path.insert(0, str(_ai_dir))

from torch_optimizations import BatchConfig, BatchProcessor  # noqa: E402

logger = logging.getLogger(__name__)

# COCO 17 keypoint names in order
KEYPOINT_NAMES: list[str] = [
    "nose",
    "left_eye",
    "right_eye",
    "left_ear",
    "right_ear",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
]

# Keypoint index lookup for convenience
KEYPOINT_INDICES: dict[str, int] = {name: idx for idx, name in enumerate(KEYPOINT_NAMES)}

# Poses that are considered suspicious in a security context
SUSPICIOUS_POSES: frozenset[str] = frozenset(
    {
        "crouching",
        "crawling",
        "hiding",
        "reaching_up",
    }
)


def _get_tensorrt_enabled() -> bool:
    """Check if TensorRT is enabled via environment variable.

    Returns:
        True if POSE_USE_TENSORRT is set to 'true', '1', or 'yes' (case-insensitive).
    """
    value = os.environ.get("POSE_USE_TENSORRT", "false").lower()
    return value in ("true", "1", "yes")


def _get_tensorrt_fp16_enabled() -> bool:
    """Check if TensorRT FP16 precision is enabled.

    Returns:
        True if POSE_TENSORRT_FP16 is set to 'true', '1', or 'yes' (default: true).
    """
    value = os.environ.get("POSE_TENSORRT_FP16", "true").lower()
    return value in ("true", "1", "yes")


def _get_tensorrt_engine_path(model_path: str) -> str:
    """Get the TensorRT engine path for a given model path.

    The engine file is placed alongside the .pt file with .engine extension.
    For example: /models/yolov8n-pose.pt -> /models/yolov8n-pose.engine

    Args:
        model_path: Path to the PyTorch model file (.pt)

    Returns:
        Path to the corresponding TensorRT engine file (.engine)
    """
    custom_path = os.environ.get("POSE_TENSORRT_ENGINE_PATH")
    if custom_path:
        return custom_path

    model_path_obj = Path(model_path)
    return str(model_path_obj.with_suffix(".engine"))


def _is_tensorrt_available() -> bool:
    """Check if TensorRT is available in the environment.

    Returns:
        True if TensorRT can be imported and CUDA is available.
    """
    if not torch.cuda.is_available():
        return False

    try:
        import tensorrt  # noqa: F401

        return True
    except ImportError:
        return False


@dataclass
class Keypoint:
    """A single body keypoint with coordinates and confidence.

    Attributes:
        name: The keypoint name (e.g., "nose", "left_shoulder")
        x: X coordinate (in pixels or normalized 0-1)
        y: Y coordinate (in pixels or normalized 0-1)
        confidence: Detection confidence (0-1)
    """

    name: str
    x: float
    y: float
    confidence: float


@dataclass
class PoseResult:
    """Result from pose estimation for a single person.

    Attributes:
        keypoints: List of detected keypoints
        pose_class: Classified pose (e.g., "standing", "crouching", "running")
        confidence: Overall pose confidence
        is_suspicious: True if pose is flagged as potentially suspicious
    """

    keypoints: list[Keypoint]
    pose_class: str
    confidence: float
    is_suspicious: bool


def validate_model_path(path: str) -> str:
    """Validate model path to prevent path traversal attacks.

    Args:
        path: The model path to validate

    Returns:
        The validated path (normalized if local)

    Raises:
        ValueError: If path contains traversal sequences
    """
    if ".." in path:
        logger.warning(f"Suspicious model path detected (traversal sequence): {path}")
        raise ValueError(f"Invalid model path: path traversal sequences not allowed: {path}")

    if path.startswith("/") or path.startswith("./"):
        abs_path = str(Path(path).resolve())
        logger.debug(f"Local model path validated: {path} -> {abs_path}")
        return abs_path

    return path


class PoseEstimator:
    """YOLOv8n-pose human pose estimation model wrapper.

    This class provides pose estimation using the YOLOv8n-pose model from
    Ultralytics. It detects 17 COCO keypoints per person and classifies
    body posture for security analysis.

    Supports:
    - True batch inference with optimal batching (NEM-3377)
    - TensorRT acceleration for 2-3x speedup (NEM-3838)

    TensorRT Support:
    - Set POSE_USE_TENSORRT=true to enable TensorRT acceleration
    - TensorRT engine is auto-exported on first run if not found
    - Falls back to PyTorch if TensorRT export fails or is unavailable

    Attributes:
        model_path: Path to the YOLOv8 pose model (.pt file or model name)
        device: Device to run inference on (e.g., "cuda:0", "cpu")
        model: The loaded YOLO model instance
        use_tensorrt: Whether TensorRT is being used for inference

    Example:
        >>> estimator = PoseEstimator("/models/yolov8n-pose.pt")
        >>> estimator.load_model()
        >>> result = estimator.estimate_pose(image)
        >>> print(f"Pose: {result.pose_class}, Suspicious: {result.is_suspicious}")

        # With TensorRT (set POSE_USE_TENSORRT=true):
        >>> estimator = PoseEstimator("/models/yolov8n-pose.pt", use_tensorrt=True)
        >>> estimator.load_model()  # Auto-exports to TensorRT if needed
    """

    def __init__(
        self,
        model_path: str,
        device: str = "cuda:0",
        max_batch_size: int = 8,
        use_tensorrt: bool | None = None,
    ) -> None:
        """Initialize pose estimator.

        Args:
            model_path: Path to YOLOv8 pose model file or model name
            device: Device to run inference on
            max_batch_size: Maximum batch size for batch inference (NEM-3377).
            use_tensorrt: Whether to use TensorRT acceleration. If None,
                         determined by POSE_USE_TENSORRT environment variable.

        Raises:
            ValueError: If model_path contains path traversal sequences
        """
        self.model_path = validate_model_path(model_path)
        self.device = device
        self.model: Any = None

        # TensorRT configuration (NEM-3838)
        if use_tensorrt is None:
            use_tensorrt = _get_tensorrt_enabled()
        self._use_tensorrt_requested = use_tensorrt
        self.use_tensorrt = False  # Will be set to True if TensorRT loads successfully

        # Batch processing configuration (NEM-3377)
        self.batch_processor = BatchProcessor(BatchConfig(max_batch_size=max_batch_size))

        logger.info(f"Initializing PoseEstimator from {self.model_path}")
        if use_tensorrt:
            logger.info("TensorRT acceleration requested")

    def _export_to_tensorrt(self) -> str | None:
        """Export the PyTorch model to TensorRT engine format.

        Uses Ultralytics native export functionality which handles all the
        complexity of ONNX conversion and TensorRT optimization.

        Returns:
            Path to the exported engine file, or None if export fails.
        """
        try:
            from ultralytics import YOLO
        except ImportError:
            logger.warning("ultralytics package not available for TensorRT export")
            return None

        engine_path = _get_tensorrt_engine_path(self.model_path)

        # Check if engine already exists
        if os.path.exists(engine_path):
            logger.info(f"TensorRT engine already exists: {engine_path}")
            return engine_path

        logger.info(f"Exporting YOLOv8n-pose to TensorRT engine: {engine_path}")
        logger.info("This may take several minutes on first run...")

        try:
            # Load the PyTorch model
            pt_model = YOLO(self.model_path)

            # Export to TensorRT using Ultralytics native export
            # This creates an .engine file in the same directory
            use_fp16 = _get_tensorrt_fp16_enabled()
            export_result = pt_model.export(
                format="engine",
                half=use_fp16,
                device=self.device.replace("cuda:", "") if "cuda" in self.device else "0",
            )

            # Ultralytics returns the path to the exported model
            if export_result and os.path.exists(str(export_result)):
                logger.info(f"TensorRT engine exported successfully: {export_result}")
                return str(export_result)

            # Check if the engine was created at the expected path
            if os.path.exists(engine_path):
                logger.info(f"TensorRT engine created at: {engine_path}")
                return engine_path

            logger.warning("TensorRT export completed but engine file not found")
            return None

        except Exception as e:
            logger.warning(f"TensorRT export failed: {e}")
            logger.info("Falling back to PyTorch inference")
            return None

    def load_model(self) -> PoseEstimator:
        """Load the YOLOv8n-pose model into memory.

        If TensorRT is requested and available, attempts to load/export
        a TensorRT engine for accelerated inference. Falls back to PyTorch
        if TensorRT is unavailable or fails.

        Returns:
            Self for method chaining

        Raises:
            ImportError: If ultralytics is not installed
            FileNotFoundError: If model file not found
        """
        try:
            from ultralytics import YOLO
        except ImportError as e:
            logger.error("ultralytics package not installed. Install with: pip install ultralytics")
            raise ImportError(
                "ultralytics package required for YOLOv8 pose estimation. "
                "Install with: pip install ultralytics"
            ) from e

        # Check if TensorRT should be used
        if self._use_tensorrt_requested:
            if not _is_tensorrt_available():
                logger.warning(
                    "TensorRT requested but not available (missing tensorrt package or CUDA). "
                    "Falling back to PyTorch."
                )
            elif "cpu" in self.device.lower():
                logger.warning("TensorRT requested but device is CPU. Falling back to PyTorch.")
            else:
                # Try to load or export TensorRT engine
                engine_path = _get_tensorrt_engine_path(self.model_path)

                if os.path.exists(engine_path):
                    logger.info(f"Loading TensorRT engine from {engine_path}...")
                    try:
                        self.model = YOLO(engine_path)
                        self.use_tensorrt = True
                        logger.info(f"PoseEstimator loaded with TensorRT on {self.device}")
                        return self
                    except Exception as e:
                        logger.warning(f"Failed to load TensorRT engine: {e}")
                        logger.info("Attempting to re-export...")

                # Export to TensorRT
                exported_path = self._export_to_tensorrt()
                if exported_path:
                    try:
                        self.model = YOLO(exported_path)
                        self.use_tensorrt = True
                        logger.info(f"PoseEstimator loaded with TensorRT on {self.device}")
                        return self
                    except Exception as e:
                        logger.warning(f"Failed to load exported TensorRT engine: {e}")

        # Fall back to PyTorch
        logger.info(f"Loading YOLOv8n-pose model from {self.model_path}...")
        self.model = YOLO(self.model_path)

        # Move to device
        if "cuda" in self.device and torch.cuda.is_available():
            self.model.to(self.device)
            logger.info(f"PoseEstimator loaded on {self.device}")
        else:
            self.device = "cpu"
            logger.info("PoseEstimator using CPU (CUDA not available)")

        logger.info("PoseEstimator loaded successfully")
        return self

    def unload(self) -> None:
        """Unload the model from memory to free VRAM."""
        if self.model is not None:
            del self.model
            self.model = None

            if torch.cuda.is_available():
                torch.cuda.empty_cache()

            logger.info(f"PoseEstimator unloaded (was using TensorRT: {self.use_tensorrt})")
            self.use_tensorrt = False

    def get_backend_info(self) -> dict[str, Any]:
        """Get information about the current inference backend.

        Returns:
            Dictionary with backend details including whether TensorRT is active.
        """
        return {
            "backend": "tensorrt" if self.use_tensorrt else "pytorch",
            "device": self.device,
            "model_path": self.model_path,
            "tensorrt_requested": self._use_tensorrt_requested,
            "tensorrt_active": self.use_tensorrt,
            "model_loaded": self.model is not None,
        }

    def estimate_pose(
        self,
        image: Image.Image | NDArray[np.uint8],
        bbox: tuple[float, float, float, float] | None = None,
    ) -> PoseResult:
        """Estimate pose for person in image/bounding box.

        Args:
            image: PIL Image or numpy array (RGB)
            bbox: Optional bounding box (x1, y1, x2, y2) to crop before estimation

        Returns:
            PoseResult with keypoints, pose classification, and suspicious flag

        Raises:
            RuntimeError: If model is not loaded
        """
        if self.model is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        # Convert PIL to numpy if needed
        image_array = np.array(image.convert("RGB")) if isinstance(image, Image.Image) else image

        # Crop to bbox if provided
        if bbox is not None:
            x1, y1, x2, y2 = bbox
            h, w = image_array.shape[:2]
            # Clamp to image bounds
            x1 = max(0, int(x1))
            y1 = max(0, int(y1))
            x2 = min(w, int(x2))
            y2 = min(h, int(y2))
            if x2 > x1 and y2 > y1:
                image_array = image_array[y1:y2, x1:x2]

        # Run inference
        results = self.model(image_array, verbose=False)

        # Handle empty results
        if not results or len(results) == 0:
            return PoseResult(
                keypoints=[],
                pose_class="unknown",
                confidence=0.0,
                is_suspicious=False,
            )

        result = results[0]

        # Check if keypoints were detected
        if result.keypoints is None or len(result.keypoints) == 0:
            return PoseResult(
                keypoints=[],
                pose_class="unknown",
                confidence=0.0,
                is_suspicious=False,
            )

        # Get keypoints for first detected person
        keypoints_data = result.keypoints[0]
        keypoints = self._format_keypoints(keypoints_data)

        # Classify pose
        pose_class = self._classify_pose(keypoints)

        # Calculate overall confidence
        confidence = self._calculate_confidence(keypoints)

        return PoseResult(
            keypoints=keypoints,
            pose_class=pose_class,
            confidence=confidence,
            is_suspicious=pose_class in SUSPICIOUS_POSES,
        )

    def estimate_poses_batch(
        self,
        images: list[Image.Image | NDArray[np.uint8]],
    ) -> list[PoseResult]:
        """Estimate poses for multiple images in batch.

        Args:
            images: List of PIL Images or numpy arrays

        Returns:
            List of PoseResult, one per image
        """
        if self.model is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        # Convert all images to numpy arrays
        image_arrays = []
        for img in images:
            if isinstance(img, Image.Image):
                image_arrays.append(np.array(img.convert("RGB")))
            else:
                image_arrays.append(img)

        # Run batch inference
        results = self.model(image_arrays, verbose=False)

        pose_results = []
        for result in results:
            if result.keypoints is None or len(result.keypoints) == 0:
                pose_results.append(
                    PoseResult(
                        keypoints=[],
                        pose_class="unknown",
                        confidence=0.0,
                        is_suspicious=False,
                    )
                )
                continue

            keypoints_data = result.keypoints[0]
            keypoints = self._format_keypoints(keypoints_data)
            pose_class = self._classify_pose(keypoints)
            confidence = self._calculate_confidence(keypoints)

            pose_results.append(
                PoseResult(
                    keypoints=keypoints,
                    pose_class=pose_class,
                    confidence=confidence,
                    is_suspicious=pose_class in SUSPICIOUS_POSES,
                )
            )

        return pose_results

    def _format_keypoints(
        self,
        keypoints_data: Any,
    ) -> list[Keypoint]:
        """Format YOLOv8 keypoints to our Keypoint format.

        Args:
            keypoints_data: YOLOv8 keypoints tensor

        Returns:
            List of Keypoint objects
        """
        keypoints: list[Keypoint] = []

        # Extract xy coordinates: shape (17, 2)
        xy = keypoints_data.xy[0].cpu().numpy()

        # Extract confidence scores if available
        if keypoints_data.conf is not None:
            conf = keypoints_data.conf[0].cpu().numpy()
        else:
            # Default to high confidence if not provided
            conf = np.ones(len(KEYPOINT_NAMES))

        for i, name in enumerate(KEYPOINT_NAMES):
            if i >= len(xy) or i >= len(conf):
                continue

            kp_confidence = float(conf[i])

            # Always add keypoint but mark low-confidence ones
            keypoints.append(
                Keypoint(
                    name=name,
                    x=float(xy[i, 0]),
                    y=float(xy[i, 1]),
                    confidence=kp_confidence,
                )
            )

        return keypoints

    def _get_keypoint_y(
        self,
        left: Keypoint | None,
        right: Keypoint | None,
        min_conf: float = 0.3,
    ) -> float | None:
        """Get average Y position from paired keypoints.

        Args:
            left: Left side keypoint
            right: Right side keypoint
            min_conf: Minimum confidence threshold

        Returns:
            Average Y position or None if insufficient confidence
        """
        if left and right and left.confidence > min_conf and right.confidence > min_conf:
            return (left.y + right.y) / 2
        if left and left.confidence > min_conf:
            return left.y
        if right and right.confidence > min_conf:
            return right.y
        return None

    def _check_reaching_up(
        self,
        nose: Keypoint | None,
        left_wrist: Keypoint | None,
        right_wrist: Keypoint | None,
    ) -> bool:
        """Check if person has wrists above head (reaching up)."""
        if not nose or nose.confidence <= 0.3:
            return False

        threshold = nose.y - 50
        left_up = left_wrist and left_wrist.confidence > 0.3 and left_wrist.y < threshold
        right_up = right_wrist and right_wrist.confidence > 0.3 and right_wrist.y < threshold
        return bool(left_up or right_up)

    def _check_crouching(
        self,
        nose: Keypoint | None,
        hip_y: float,
        shoulder_y: float | None,
        knee_y: float | None,
    ) -> bool:
        """Check if person is in crouching position."""
        if not nose or nose.confidence <= 0.3:
            return False

        # If torso is very compressed (nose close to hips)
        if shoulder_y is not None and knee_y is not None:
            torso_length = abs(hip_y - shoulder_y)
            if torso_length < 50 or nose.y > hip_y * 0.85:
                return True

        # Alternative: check if hips are close to knees (squatting)
        return knee_y is not None and abs(knee_y - hip_y) < 30

    def _check_running(
        self,
        left_ankle: Keypoint | None,
        right_ankle: Keypoint | None,
    ) -> bool:
        """Check if person is running (wide leg spread)."""
        if not (left_ankle and right_ankle):
            return False
        if left_ankle.confidence <= 0.3 or right_ankle.confidence <= 0.3:
            return False
        leg_spread = abs(left_ankle.x - right_ankle.x)
        return leg_spread > 100

    def _classify_pose(self, keypoints: list[Keypoint]) -> str:  # noqa: PLR0911
        """Classify pose based on keypoint positions.

        Uses geometric relationships between keypoints to determine body posture.

        Args:
            keypoints: List of detected keypoints

        Returns:
            Pose classification string (e.g., "standing", "crouching")
        """
        if not keypoints:
            return "unknown"

        # Create lookup dict for easier access
        kp_dict: dict[str, Keypoint] = {kp.name: kp for kp in keypoints}

        # Get key body parts
        nose = kp_dict.get("nose")
        left_hip = kp_dict.get("left_hip")
        right_hip = kp_dict.get("right_hip")
        left_knee = kp_dict.get("left_knee")
        right_knee = kp_dict.get("right_knee")
        left_ankle = kp_dict.get("left_ankle")
        right_ankle = kp_dict.get("right_ankle")
        left_wrist = kp_dict.get("left_wrist")
        right_wrist = kp_dict.get("right_wrist")
        left_shoulder = kp_dict.get("left_shoulder")
        right_shoulder = kp_dict.get("right_shoulder")

        # Calculate body segment Y positions
        hip_y = self._get_keypoint_y(left_hip, right_hip)
        if hip_y is None:
            return "unknown"

        shoulder_y = self._get_keypoint_y(left_shoulder, right_shoulder)
        knee_y = self._get_keypoint_y(left_knee, right_knee)
        ankle_y = self._get_keypoint_y(left_ankle, right_ankle)

        # Check poses in order of specificity
        if self._check_reaching_up(nose, left_wrist, right_wrist):
            return "reaching_up"

        if self._check_crouching(nose, hip_y, shoulder_y, knee_y):
            return "crouching"

        if self._check_running(left_ankle, right_ankle):
            return "running"

        # Check for crawling: horizontal body with spread limbs
        if shoulder_y is not None and ankle_y is not None:
            vertical_span = abs(shoulder_y - ankle_y)
            if vertical_span < 100:
                return "crawling"

        return "standing"

    def _calculate_confidence(self, keypoints: list[Keypoint]) -> float:
        """Calculate overall pose confidence from individual keypoint confidences.

        Args:
            keypoints: List of detected keypoints

        Returns:
            Average confidence score (0-1)
        """
        if not keypoints:
            return 0.0

        total_conf = sum(kp.confidence for kp in keypoints)
        return round(total_conf / len(keypoints), 4)


def load_pose_estimator(
    model_path: str | None = None,
    device: str = "cuda:0",
    use_tensorrt: bool | None = None,
) -> PoseEstimator:
    """Factory function to create and load a PoseEstimator.

    Args:
        model_path: Path to YOLOv8 pose model. Defaults to "yolov8n-pose.pt"
        device: Device to run inference on
        use_tensorrt: Whether to use TensorRT acceleration. If None,
                     determined by POSE_USE_TENSORRT environment variable.

    Returns:
        Loaded PoseEstimator instance
    """
    if model_path is None:
        model_path = "yolov8n-pose.pt"

    estimator = PoseEstimator(model_path, device, use_tensorrt=use_tensorrt)
    estimator.load_model()
    return estimator
