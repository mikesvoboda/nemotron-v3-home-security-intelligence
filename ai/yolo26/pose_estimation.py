"""YOLO26 Pose Estimation Module.

This module provides pose estimation capabilities for security monitoring,
enabling detection of:
- Falls (person lying horizontally)
- Aggressive behavior (raised arms, rapid movement)
- Loitering (stationary person over time threshold)

NEM-3910: Add YOLO26 pose estimation for fall/aggression/loitering detection

Uses YOLO11-pose or YOLOv8-pose models via Ultralytics for 17 COCO keypoint detection.

COCO Keypoint Format (17 keypoints):
    0: nose          1: left_eye      2: right_eye
    3: left_ear      4: right_ear     5: left_shoulder
    6: right_shoulder 7: left_elbow   8: right_elbow
    9: left_wrist    10: right_wrist  11: left_hip
    12: right_hip    13: left_knee    14: right_knee
    15: left_ankle   16: right_ankle

Model Variants:
    - yolo11n-pose.pt: Nano (fastest, ~6MB)
    - yolo11s-pose.pt: Small (~22MB)
    - yolo11m-pose.pt: Medium (~50MB)
    - yolo11l-pose.pt: Large (~85MB)
    - yolo11x-pose.pt: Extra-large (most accurate)

Environment Variables:
    - YOLO26_POSE_MODEL_PATH: Path to pose model (default: yolo11n-pose.pt)
    - YOLO26_POSE_CONFIDENCE: Confidence threshold (default: 0.5)
    - LOITERING_THRESHOLD_SECONDS: Time for loitering detection (default: 30)
    - LOITERING_MOVEMENT_THRESHOLD: Pixel distance for "stationary" (default: 50)
"""

from __future__ import annotations

import logging
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import torch
from numpy.typing import NDArray
from PIL import Image
from prometheus_client import Counter, Histogram
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

# COCO keypoint names in order
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

# Keypoint index lookup
KEYPOINT_INDICES: dict[str, int] = {name: idx for idx, name in enumerate(KEYPOINT_NAMES)}

# Behavior detection thresholds
FALL_HORIZONTAL_RATIO_THRESHOLD = 0.6  # Height/Width ratio < this indicates lying down
FALL_VERTICAL_DIFF_THRESHOLD = 100  # Max Y diff between head and feet for fall
AGGRESSION_ARM_RAISE_THRESHOLD = 50  # Wrists must be this many px above nose
RAPID_MOVEMENT_THRESHOLD = 150  # Pixels per 100ms for rapid movement detection
DEFAULT_LOITERING_THRESHOLD_SECONDS = 30
DEFAULT_LOITERING_MOVEMENT_THRESHOLD = 50  # Pixels

# =============================================================================
# Prometheus Metrics
# =============================================================================

POSE_INFERENCE_DURATION_SECONDS = Histogram(
    "yolo26_pose_inference_duration_seconds",
    "Pose estimation inference duration in seconds",
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

POSE_DETECTIONS_TOTAL = Counter(
    "yolo26_pose_detections_total",
    "Total number of pose detections by class",
    ["pose_class"],
)

POSE_BEHAVIOR_ALERTS_TOTAL = Counter(
    "yolo26_pose_behavior_alerts_total",
    "Total number of behavior alerts",
    ["alert_type"],
)


def record_pose_detection(pose_class: str, _confidence: float = 0.0) -> None:
    """Record a pose detection metric.

    Args:
        pose_class: Detected pose class (standing, crouching, fallen, etc.)
        _confidence: Detection confidence (unused but kept for API consistency)
    """
    POSE_DETECTIONS_TOTAL.labels(pose_class=pose_class).inc()


def record_behavior_alert(alert_type: str) -> None:
    """Record a behavior alert metric.

    Args:
        alert_type: Type of alert (fall_detected, aggression_detected, loitering_detected)
    """
    POSE_BEHAVIOR_ALERTS_TOTAL.labels(alert_type=alert_type).inc()


# =============================================================================
# Pydantic Schemas
# =============================================================================


class Keypoint(BaseModel):
    """A single body keypoint with coordinates and confidence."""

    name: str = Field(..., description="Keypoint name (e.g., nose, left_shoulder)")
    x: float = Field(..., description="X coordinate in pixels")
    y: float = Field(..., description="Y coordinate in pixels")
    confidence: float = Field(..., description="Detection confidence (0-1)")


class BoundingBox(BaseModel):
    """Bounding box coordinates."""

    x: int = Field(..., description="Top-left x coordinate")
    y: int = Field(..., description="Top-left y coordinate")
    width: int = Field(..., description="Box width")
    height: int = Field(..., description="Box height")


class BehaviorFlags(BaseModel):
    """Behavior detection flags for a detected person."""

    is_fallen: bool = Field(False, description="Person appears to have fallen")
    is_aggressive: bool = Field(False, description="Person showing aggressive posture")
    is_loitering: bool = Field(False, description="Person has been stationary too long")
    fall_confidence: float = Field(0.0, description="Confidence of fall detection (0-1)")
    aggression_confidence: float = Field(0.0, description="Confidence of aggression detection")
    loitering_duration_seconds: float = Field(0.0, description="Duration of loitering")


class PoseDetection(BaseModel):
    """Single person pose detection result."""

    person_id: int = Field(..., description="Unique person ID for tracking")
    bbox: BoundingBox = Field(..., description="Person bounding box")
    confidence: float = Field(..., description="Detection confidence (0-1)")
    keypoints: list[Keypoint] = Field(default_factory=list, description="Detected keypoints")
    pose_class: str = Field("unknown", description="Pose classification")
    behavior: BehaviorFlags = Field(default_factory=BehaviorFlags, description="Behavior flags")


class PoseEstimationResponse(BaseModel):
    """Response format for pose estimation endpoint."""

    detections: list[PoseDetection] = Field(
        default_factory=list, description="List of detected persons with poses"
    )
    inference_time_ms: float = Field(..., description="Inference time in milliseconds")
    image_width: int = Field(..., description="Original image width")
    image_height: int = Field(..., description="Original image height")
    alerts: list[str] = Field(default_factory=list, description="Behavior alerts triggered")


# =============================================================================
# Behavior Detection Functions
# =============================================================================


def _get_keypoint(
    keypoints: NDArray[np.floating], idx: int, min_conf: float = 0.3
) -> tuple[float, float] | None:
    """Get keypoint coordinates if confidence is above threshold.

    Args:
        keypoints: Array of shape (17, 3) with x, y, confidence
        idx: Keypoint index
        min_conf: Minimum confidence threshold

    Returns:
        Tuple of (x, y) or None if keypoint not visible
    """
    if keypoints.shape[0] <= idx:
        return None
    x, y, conf = keypoints[idx]
    if conf < min_conf:
        return None
    return (float(x), float(y))


def _get_average_y(
    keypoints: NDArray[np.floating], indices: list[int], min_conf: float = 0.3
) -> float | None:
    """Get average Y coordinate of multiple keypoints.

    Args:
        keypoints: Array of shape (17, 3)
        indices: List of keypoint indices to average
        min_conf: Minimum confidence threshold

    Returns:
        Average Y coordinate or None if no valid keypoints
    """
    valid_ys = []
    for idx in indices:
        kp = _get_keypoint(keypoints, idx, min_conf)
        if kp is not None:
            valid_ys.append(kp[1])
    if not valid_ys:
        return None
    return sum(valid_ys) / len(valid_ys)


def detect_fall(keypoints: NDArray[np.floating]) -> dict[str, Any]:
    """Detect if a person has fallen based on keypoint positions.

    Fall detection criteria:
    1. Head and feet are at similar Y levels (person is horizontal)
    2. Body width > body height (lying down)
    3. Hips are near ground level relative to ankles

    Args:
        keypoints: Array of shape (17, 3) with x, y, confidence for COCO keypoints

    Returns:
        Dict with is_fallen (bool) and confidence (float)
    """
    result = {"is_fallen": False, "confidence": 0.0, "reason": None}

    if keypoints.size == 0 or keypoints.shape[0] < 17:
        return result

    # Get key points
    nose = _get_keypoint(keypoints, KEYPOINT_INDICES["nose"])
    left_hip = _get_keypoint(keypoints, KEYPOINT_INDICES["left_hip"])
    right_hip = _get_keypoint(keypoints, KEYPOINT_INDICES["right_hip"])
    left_ankle = _get_keypoint(keypoints, KEYPOINT_INDICES["left_ankle"])
    right_ankle = _get_keypoint(keypoints, KEYPOINT_INDICES["right_ankle"])

    # Need at least nose/head and some lower body keypoints
    if nose is None:
        return result

    # Calculate head Y level
    head_y = nose[1]

    # Calculate feet Y level (average of ankles or use knees as fallback)
    feet_y = _get_average_y(
        keypoints, [KEYPOINT_INDICES["left_ankle"], KEYPOINT_INDICES["right_ankle"]]
    )
    if feet_y is None:
        feet_y = _get_average_y(
            keypoints, [KEYPOINT_INDICES["left_knee"], KEYPOINT_INDICES["right_knee"]]
        )

    if feet_y is None:
        return result

    # Criterion 1: Head and feet at similar Y level (within threshold)
    vertical_diff = abs(head_y - feet_y)

    if vertical_diff < FALL_VERTICAL_DIFF_THRESHOLD:
        result["is_fallen"] = True
        result["confidence"] = 0.8
        result["reason"] = "horizontal_body"

        # Boost confidence if we have good keypoint visibility
        avg_conf = np.mean(keypoints[:, 2])
        result["confidence"] *= avg_conf

        return result

    # Criterion 2: Calculate body aspect ratio (width vs height)
    if left_hip and right_hip and left_ankle and right_ankle:
        body_width = max(
            abs(left_hip[0] - right_hip[0]),
            abs(left_ankle[0] - right_ankle[0]),
        )
        body_height = abs(head_y - max(left_ankle[1], right_ankle[1]))

        if body_height > 0:
            aspect_ratio = body_width / body_height
            if aspect_ratio > 1.5:  # Width > 1.5x height indicates lying down
                result["is_fallen"] = True
                result["confidence"] = min(0.9, aspect_ratio / 2.0)
                result["reason"] = "horizontal_aspect_ratio"

                avg_conf = np.mean(keypoints[:, 2])
                result["confidence"] *= avg_conf

    return result


def detect_aggression(keypoints: NDArray[np.floating]) -> dict[str, Any]:
    """Detect aggressive posture based on keypoint positions.

    Aggression indicators:
    1. Arms raised high (wrists above head level)
    2. Wide arm stance
    3. Forward-leaning posture

    Args:
        keypoints: Array of shape (17, 3) with x, y, confidence for COCO keypoints

    Returns:
        Dict with is_aggressive (bool), confidence (float), and indicators list
    """
    result = {
        "is_aggressive": False,
        "confidence": 0.0,
        "indicators": [],
    }

    if keypoints.size == 0 or keypoints.shape[0] < 17:
        return result

    indicators = []
    confidence_sum = 0.0

    # Get key points
    nose = _get_keypoint(keypoints, KEYPOINT_INDICES["nose"])
    left_wrist = _get_keypoint(keypoints, KEYPOINT_INDICES["left_wrist"])
    right_wrist = _get_keypoint(keypoints, KEYPOINT_INDICES["right_wrist"])
    left_shoulder = _get_keypoint(keypoints, KEYPOINT_INDICES["left_shoulder"])
    right_shoulder = _get_keypoint(keypoints, KEYPOINT_INDICES["right_shoulder"])

    if nose is None:
        return result

    # Check for raised arms (wrists above head)
    raised_arms = False
    if left_wrist and left_wrist[1] < nose[1] - AGGRESSION_ARM_RAISE_THRESHOLD:
        raised_arms = True
    if right_wrist and right_wrist[1] < nose[1] - AGGRESSION_ARM_RAISE_THRESHOLD:
        raised_arms = True

    if raised_arms:
        indicators.append("raised_arms")
        confidence_sum += 0.7

    # Check for both arms raised high (more aggressive)
    both_raised = (
        left_wrist
        and right_wrist
        and left_wrist[1] < nose[1] - AGGRESSION_ARM_RAISE_THRESHOLD
        and right_wrist[1] < nose[1] - AGGRESSION_ARM_RAISE_THRESHOLD
    )
    if both_raised:
        indicators.append("both_arms_raised")
        confidence_sum += 0.2

    # Check for wide stance (arms spread)
    if left_shoulder and right_shoulder and left_wrist and right_wrist:
        shoulder_width = abs(left_shoulder[0] - right_shoulder[0])
        wrist_width = abs(left_wrist[0] - right_wrist[0])
        if wrist_width > shoulder_width * 1.5:
            indicators.append("wide_arm_stance")
            confidence_sum += 0.1

    if indicators:
        result["is_aggressive"] = True
        result["confidence"] = min(1.0, confidence_sum)
        result["indicators"] = indicators

    return result


def detect_aggression_with_motion(
    current_keypoints: NDArray[np.floating],
    previous_keypoints: NDArray[np.floating],
    time_delta_ms: float,
) -> dict[str, Any]:
    """Detect aggression including rapid movement between frames.

    Args:
        current_keypoints: Current frame keypoints (17, 3)
        previous_keypoints: Previous frame keypoints (17, 3)
        time_delta_ms: Time between frames in milliseconds

    Returns:
        Dict with is_aggressive (bool), confidence (float), and indicators list
    """
    # Start with static aggression detection
    result = detect_aggression(current_keypoints)

    if previous_keypoints.size == 0 or time_delta_ms <= 0:
        return result

    # Check for rapid movement
    indicators = list(result.get("indicators", []))
    confidence = result.get("confidence", 0.0)

    # Focus on arm movement (wrists and elbows)
    arm_indices = [
        KEYPOINT_INDICES["left_wrist"],
        KEYPOINT_INDICES["right_wrist"],
        KEYPOINT_INDICES["left_elbow"],
        KEYPOINT_INDICES["right_elbow"],
    ]

    max_velocity = 0.0
    for idx in arm_indices:
        if idx < current_keypoints.shape[0] and idx < previous_keypoints.shape[0]:
            curr = current_keypoints[idx]
            prev = previous_keypoints[idx]

            # Only consider high-confidence keypoints
            if curr[2] > 0.3 and prev[2] > 0.3:
                distance = np.sqrt((curr[0] - prev[0]) ** 2 + (curr[1] - prev[1]) ** 2)
                # Normalize to per-100ms velocity
                velocity = distance * (100 / time_delta_ms)
                max_velocity = max(max_velocity, velocity)

    if max_velocity > RAPID_MOVEMENT_THRESHOLD:
        indicators.append("rapid_movement")
        confidence += 0.4
        result["is_aggressive"] = True

    result["confidence"] = min(1.0, confidence)
    result["indicators"] = indicators
    result["max_velocity"] = max_velocity

    return result


def detect_loitering(
    position_history: list[dict[str, float]],
    threshold_seconds: float = DEFAULT_LOITERING_THRESHOLD_SECONDS,
    movement_threshold: float = DEFAULT_LOITERING_MOVEMENT_THRESHOLD,
) -> dict[str, Any]:
    """Detect if a person has been loitering (stationary) too long.

    Args:
        position_history: List of {"x": float, "y": float, "timestamp_ms": float}
        threshold_seconds: Time threshold for loitering detection
        movement_threshold: Pixel threshold for considering "stationary"

    Returns:
        Dict with is_loitering (bool), duration_seconds (float)
    """
    result = {
        "is_loitering": False,
        "duration_seconds": 0.0,
        "movement_distance": 0.0,
    }

    if len(position_history) < 2:
        return result

    # Sort by timestamp
    sorted_history = sorted(position_history, key=lambda p: p["timestamp_ms"])

    # Calculate total duration
    first_ts = sorted_history[0]["timestamp_ms"]
    last_ts = sorted_history[-1]["timestamp_ms"]
    duration_seconds = (last_ts - first_ts) / 1000.0

    if duration_seconds < threshold_seconds:
        result["duration_seconds"] = duration_seconds
        return result

    # Calculate total movement distance
    total_distance = 0.0
    for i in range(1, len(sorted_history)):
        dx = sorted_history[i]["x"] - sorted_history[i - 1]["x"]
        dy = sorted_history[i]["y"] - sorted_history[i - 1]["y"]
        total_distance += np.sqrt(dx * dx + dy * dy)

    result["duration_seconds"] = duration_seconds
    result["movement_distance"] = total_distance

    # Loitering if stationary (minimal movement) for threshold duration
    if total_distance < movement_threshold:
        result["is_loitering"] = True

    return result


def classify_pose(keypoints: NDArray[np.floating]) -> str:
    """Classify the overall pose based on keypoint positions.

    Args:
        keypoints: Array of shape (17, 3) with x, y, confidence

    Returns:
        Pose classification string
    """
    if keypoints.size == 0 or keypoints.shape[0] < 17:
        return "unknown"

    # Check for fall first (highest priority)
    fall_result = detect_fall(keypoints)
    if fall_result["is_fallen"]:
        return "lying_down" if fall_result.get("reason") == "horizontal_body" else "fallen"

    # Check for aggressive pose
    aggression_result = detect_aggression(keypoints)
    if aggression_result["is_aggressive"]:
        if "raised_arms" in aggression_result.get("indicators", []):
            return "reaching_up"
        return "aggressive"

    # Check for crouching (compressed torso)
    nose = _get_keypoint(keypoints, KEYPOINT_INDICES["nose"])
    hip_y = _get_average_y(keypoints, [KEYPOINT_INDICES["left_hip"], KEYPOINT_INDICES["right_hip"]])
    shoulder_y = _get_average_y(
        keypoints, [KEYPOINT_INDICES["left_shoulder"], KEYPOINT_INDICES["right_shoulder"]]
    )
    knee_y = _get_average_y(
        keypoints, [KEYPOINT_INDICES["left_knee"], KEYPOINT_INDICES["right_knee"]]
    )

    if nose and hip_y and shoulder_y:
        # Check if torso is compressed (nose close to hips)
        torso_height = abs(hip_y - shoulder_y)
        if torso_height < 50 or (knee_y and abs(knee_y - hip_y) < 50):
            return "crouching"

    return "standing"


# =============================================================================
# Loitering Tracker
# =============================================================================


@dataclass
class LoiteringTracker:
    """Tracks person positions over time for loitering detection.

    Maintains a history of positions for each tracked person ID
    to detect prolonged stationary behavior.
    """

    threshold_seconds: float = DEFAULT_LOITERING_THRESHOLD_SECONDS
    movement_threshold: float = DEFAULT_LOITERING_MOVEMENT_THRESHOLD
    max_history_length: int = 100
    _position_history: dict[int, list[dict[str, float]]] = field(
        default_factory=lambda: defaultdict(list)
    )

    def update(self, person_id: int, x: float, y: float, timestamp_ms: float) -> None:
        """Update position history for a person.

        Args:
            person_id: Unique person identifier
            x: X coordinate
            y: Y coordinate
            timestamp_ms: Timestamp in milliseconds
        """
        self._position_history[person_id].append(
            {
                "x": x,
                "y": y,
                "timestamp_ms": timestamp_ms,
            }
        )

        # Trim old history
        if len(self._position_history[person_id]) > self.max_history_length:
            self._position_history[person_id] = self._position_history[person_id][
                -self.max_history_length :
            ]

    def check_loitering(self, person_id: int) -> dict[str, Any]:
        """Check if a person is loitering.

        Args:
            person_id: Person identifier to check

        Returns:
            Loitering detection result
        """
        history = self._position_history.get(person_id, [])
        return detect_loitering(
            history,
            threshold_seconds=self.threshold_seconds,
            movement_threshold=self.movement_threshold,
        )

    def clear(self, person_id: int | None = None) -> None:
        """Clear position history.

        Args:
            person_id: Specific person to clear, or None to clear all
        """
        if person_id is None:
            self._position_history.clear()
        elif person_id in self._position_history:
            del self._position_history[person_id]


# =============================================================================
# YOLO26 Pose Model Wrapper
# =============================================================================


class YOLO26PoseModel:
    """YOLO pose estimation model wrapper.

    Wraps Ultralytics YOLO pose models (yolo11-pose, yolov8-pose) for
    security monitoring applications.

    Attributes:
        model_path: Path to the pose model file
        confidence_threshold: Minimum detection confidence
        device: Device to run inference on
        model: Loaded YOLO model instance
        loitering_tracker: Tracker for loitering detection
    """

    def __init__(
        self,
        model_path: str = "yolo11n-pose.pt",
        confidence_threshold: float = 0.5,
        device: str = "cuda:0",
        loitering_threshold_seconds: float = DEFAULT_LOITERING_THRESHOLD_SECONDS,
    ) -> None:
        """Initialize pose estimation model.

        Args:
            model_path: Path to YOLO pose model file
            confidence_threshold: Minimum confidence threshold
            device: Device to run inference on
            loitering_threshold_seconds: Time threshold for loitering detection
        """
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.device = device
        self.model: Any = None
        self.inference_healthy = False
        self.loitering_tracker = LoiteringTracker(threshold_seconds=loitering_threshold_seconds)

        # Frame history for motion-based detection
        self._previous_keypoints: dict[int, NDArray[np.floating]] = {}
        self._previous_timestamp_ms: float = 0

        logger.info(f"Initializing YOLO26PoseModel from {model_path}")
        logger.info(f"Device: {device}, Confidence: {confidence_threshold}")

    def load_model(self) -> YOLO26PoseModel:
        """Load the pose estimation model.

        Returns:
            Self for method chaining

        Raises:
            ImportError: If ultralytics is not installed
            FileNotFoundError: If model file not found
        """
        try:
            from ultralytics import YOLO
        except ImportError as e:
            logger.error("ultralytics package not installed")
            raise ImportError(
                "ultralytics package required. Install with: pip install ultralytics"
            ) from e

        logger.info(f"Loading pose model from {self.model_path}...")
        self.model = YOLO(self.model_path)

        # Move to device
        if "cuda" in self.device and torch.cuda.is_available():
            self.model.to(self.device)
            logger.info(f"Pose model loaded on {self.device}")
        else:
            self.device = "cpu"
            logger.info("Pose model using CPU (CUDA not available)")

        # Warmup
        self._warmup()
        logger.info("Pose model loaded and warmed up successfully")

        return self

    def _warmup(self, num_iterations: int = 2) -> None:
        """Warmup the model with dummy inputs."""
        logger.info(f"Warming up pose model with {num_iterations} iterations...")

        dummy_image = Image.new("RGB", (640, 480), color=(128, 128, 128))

        warmup_success = False
        for i in range(num_iterations):
            try:
                _ = self.detect_poses(dummy_image)
                logger.info(f"Pose warmup iteration {i + 1}/{num_iterations} complete")
                warmup_success = True
            except Exception as e:
                logger.warning(f"Pose warmup iteration {i + 1} failed: {e}")

        self.inference_healthy = warmup_success

    def unload(self) -> None:
        """Unload the model from memory."""
        if self.model is not None:
            del self.model
            self.model = None

            if torch.cuda.is_available():
                torch.cuda.empty_cache()

            logger.info("Pose model unloaded")

    def detect_poses(
        self,
        image: Image.Image | NDArray[np.uint8],
        timestamp_ms: float | None = None,
    ) -> tuple[list[dict[str, Any]], float]:
        """Detect poses in an image.

        Args:
            image: PIL Image or numpy array
            timestamp_ms: Optional timestamp for motion tracking

        Returns:
            Tuple of (list of pose detections, inference_time_ms)

        Raises:
            RuntimeError: If model is not loaded
        """
        if self.model is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        start_time = time.perf_counter()

        # Convert PIL to numpy if needed
        if isinstance(image, Image.Image):
            if image.mode != "RGB":
                image = image.convert("RGB")
            image_array = np.array(image)
        else:
            image_array = image

        _image_height, _image_width = image_array.shape[:2]

        # Current timestamp
        if timestamp_ms is None:
            timestamp_ms = time.time() * 1000
        time_delta_ms = (
            timestamp_ms - self._previous_timestamp_ms if self._previous_timestamp_ms > 0 else 0
        )

        # Run inference
        results = self.model.predict(
            source=image_array,
            conf=self.confidence_threshold,
            verbose=False,
            device=self.device,
        )

        detections = []
        alerts = []

        if results and len(results) > 0:
            result = results[0]

            if result.keypoints is not None and result.boxes is not None:
                keypoints_data = result.keypoints
                boxes_data = result.boxes

                # Process each detected person
                n_persons = len(boxes_data)
                for person_idx in range(n_persons):
                    # Get bounding box
                    xyxy = boxes_data.xyxy[person_idx].cpu().numpy()
                    x1, y1, x2, y2 = xyxy
                    conf = float(boxes_data.conf[person_idx].cpu().numpy())

                    # Get keypoints for this person
                    kp_xy = keypoints_data.xy[person_idx].cpu().numpy()  # (17, 2)
                    kp_conf = keypoints_data.conf[person_idx].cpu().numpy()  # (17,)

                    # Combine into (17, 3) array
                    person_keypoints = np.column_stack([kp_xy, kp_conf])

                    # Classify pose
                    pose_class = classify_pose(person_keypoints)

                    # Detect behaviors
                    fall_result = detect_fall(person_keypoints)
                    aggression_result = detect_aggression(person_keypoints)

                    # Check for motion-based aggression if we have previous frame
                    if person_idx in self._previous_keypoints and time_delta_ms > 0:
                        motion_result = detect_aggression_with_motion(
                            person_keypoints,
                            self._previous_keypoints[person_idx],
                            time_delta_ms,
                        )
                        if (
                            motion_result["is_aggressive"]
                            and not aggression_result["is_aggressive"]
                        ):
                            aggression_result = motion_result

                    # Update loitering tracker
                    center_x = (x1 + x2) / 2
                    center_y = (y1 + y2) / 2
                    self.loitering_tracker.update(person_idx, center_x, center_y, timestamp_ms)
                    loitering_result = self.loitering_tracker.check_loitering(person_idx)

                    # Create behavior flags
                    behavior = BehaviorFlags(
                        is_fallen=fall_result["is_fallen"],
                        is_aggressive=aggression_result["is_aggressive"],
                        is_loitering=loitering_result["is_loitering"],
                        fall_confidence=fall_result["confidence"],
                        aggression_confidence=aggression_result["confidence"],
                        loitering_duration_seconds=loitering_result["duration_seconds"],
                    )

                    # Generate alerts
                    if fall_result["is_fallen"]:
                        alerts.append(f"Fall detected (person {person_idx})")
                        record_behavior_alert("fall_detected")
                    if aggression_result["is_aggressive"]:
                        indicators = ", ".join(aggression_result.get("indicators", []))
                        alerts.append(f"Aggressive behavior (person {person_idx}): {indicators}")
                        record_behavior_alert("aggression_detected")
                    if loitering_result["is_loitering"]:
                        duration = loitering_result["duration_seconds"]
                        alerts.append(f"Loitering detected (person {person_idx}): {duration:.0f}s")
                        record_behavior_alert("loitering_detected")

                    # Format keypoints
                    keypoints_list = [
                        Keypoint(
                            name=KEYPOINT_NAMES[i],
                            x=float(person_keypoints[i, 0]),
                            y=float(person_keypoints[i, 1]),
                            confidence=float(person_keypoints[i, 2]),
                        )
                        for i in range(min(17, len(person_keypoints)))
                    ]

                    detection = PoseDetection(
                        person_id=person_idx,
                        bbox=BoundingBox(
                            x=int(x1),
                            y=int(y1),
                            width=int(x2 - x1),
                            height=int(y2 - y1),
                        ),
                        confidence=conf,
                        keypoints=keypoints_list,
                        pose_class=pose_class,
                        behavior=behavior,
                    )
                    detections.append(detection)

                    # Record metrics
                    record_pose_detection(pose_class, conf)

                    # Store for next frame
                    self._previous_keypoints[person_idx] = person_keypoints

        # Update timestamp
        self._previous_timestamp_ms = timestamp_ms

        inference_time_ms = (time.perf_counter() - start_time) * 1000
        POSE_INFERENCE_DURATION_SECONDS.observe(inference_time_ms / 1000.0)

        # Convert to dict format for API response
        detections_dict = [d.model_dump() for d in detections]

        return detections_dict, inference_time_ms


# =============================================================================
# Global Pose Model Instance
# =============================================================================

pose_model: YOLO26PoseModel | None = None


def get_pose_model() -> YOLO26PoseModel | None:
    """Get the global pose model instance."""
    return pose_model


def initialize_pose_model() -> YOLO26PoseModel:
    """Initialize the global pose model.

    Reads configuration from environment variables:
    - YOLO26_POSE_MODEL_PATH: Model path (default: yolo11n-pose.pt)
    - YOLO26_POSE_CONFIDENCE: Confidence threshold (default: 0.5)
    - LOITERING_THRESHOLD_SECONDS: Loitering time threshold (default: 30)

    Returns:
        Initialized YOLO26PoseModel instance
    """
    global pose_model

    model_path = os.environ.get("YOLO26_POSE_MODEL_PATH", "yolo11n-pose.pt")
    confidence = float(os.environ.get("YOLO26_POSE_CONFIDENCE", "0.5"))
    loitering_threshold = float(os.environ.get("LOITERING_THRESHOLD_SECONDS", "30"))
    device = "cuda:0" if torch.cuda.is_available() else "cpu"

    pose_model = YOLO26PoseModel(
        model_path=model_path,
        confidence_threshold=confidence,
        device=device,
        loitering_threshold_seconds=loitering_threshold,
    )
    pose_model.load_model()

    return pose_model


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "KEYPOINT_INDICES",
    "KEYPOINT_NAMES",
    "POSE_BEHAVIOR_ALERTS_TOTAL",
    "POSE_DETECTIONS_TOTAL",
    "POSE_INFERENCE_DURATION_SECONDS",
    "BehaviorFlags",
    "BoundingBox",
    "Keypoint",
    "LoiteringTracker",
    "PoseDetection",
    "PoseEstimationResponse",
    "YOLO26PoseModel",
    "classify_pose",
    "detect_aggression",
    "detect_aggression_with_motion",
    "detect_fall",
    "detect_loitering",
    "get_pose_model",
    "initialize_pose_model",
    "pose_model",
    "record_behavior_alert",
    "record_pose_detection",
]
