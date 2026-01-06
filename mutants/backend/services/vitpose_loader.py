"""ViTPose+ Small model loader for human pose estimation.

This module provides async loading of ViTPose+ Small model for detecting
human body keypoints, enabling pose classification for security analysis.

ViTPose+ Small is a Vision Transformer-based pose estimation model that outputs
17 COCO keypoints: nose, eyes, ears, shoulders, elbows, wrists, hips, knees, ankles.

Model Details:
    - HuggingFace: usyd-community/vitpose-plus-small
    - Parameters: 33M
    - VRAM: ~1.5GB (float16)
    - License: Apache 2.0

Pose Classification:
    - standing: upright posture with hip-knee-ankle alignment
    - crouching: knees bent significantly below hip level
    - running: leg spread with arm motion patterns
    - sitting: hips below knee level
    - lying: horizontal body orientation
    - unknown: insufficient keypoint confidence
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

from backend.core.logging import get_logger

if TYPE_CHECKING:
    from PIL import Image

logger = get_logger(__name__)


# COCO keypoint indices for pose analysis
class KeypointIndex(Enum):
    """COCO keypoint indices for pose estimation."""

    NOSE = 0
    LEFT_EYE = 1
    RIGHT_EYE = 2
    LEFT_EAR = 3
    RIGHT_EAR = 4
    LEFT_SHOULDER = 5
    RIGHT_SHOULDER = 6
    LEFT_ELBOW = 7
    RIGHT_ELBOW = 8
    LEFT_WRIST = 9
    RIGHT_WRIST = 10
    LEFT_HIP = 11
    RIGHT_HIP = 12
    LEFT_KNEE = 13
    RIGHT_KNEE = 14
    LEFT_ANKLE = 15
    RIGHT_ANKLE = 16


# Keypoint names for output
KEYPOINT_NAMES = [
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


@dataclass
class Keypoint:
    """A single detected keypoint with position and confidence.

    Attributes:
        x: X coordinate (0-1 normalized or pixel value)
        y: Y coordinate (0-1 normalized or pixel value)
        confidence: Detection confidence (0-1)
        name: Keypoint name (e.g., "left_shoulder")
    """

    x: float
    y: float
    confidence: float
    name: str


@dataclass
class PoseResult:
    """Result of pose estimation for a single person.

    Attributes:
        keypoints: Dictionary mapping keypoint names to Keypoint objects
        pose_class: Classified pose type (standing, crouching, running, etc.)
        pose_confidence: Confidence in the pose classification (0-1)
        bbox: Optional bounding box [x1, y1, x2, y2] for the person
    """

    keypoints: dict[str, Keypoint]
    pose_class: str
    pose_confidence: float
    bbox: list[float] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "keypoints": {
                name: {"x": kp.x, "y": kp.y, "confidence": kp.confidence}
                for name, kp in self.keypoints.items()
            },
            "pose_class": self.pose_class,
            "pose_confidence": self.pose_confidence,
            "bbox": self.bbox,
        }


async def load_vitpose_model(model_path: str) -> Any:
    """Load ViTPose+ Small model from HuggingFace.

    This function loads the ViTPose+ Small model for human pose estimation.
    The model detects 17 COCO keypoints for body pose analysis.

    Args:
        model_path: HuggingFace model path (e.g., "usyd-community/vitpose-plus-small")

    Returns:
        Tuple of (model, processor) for inference

    Raises:
        ImportError: If transformers or torch is not installed
        RuntimeError: If model loading fails
    """
    try:
        import torch
        from transformers import AutoProcessor, VitPoseForPoseEstimation

        logger.info(f"Loading ViTPose model from {model_path}")

        loop = asyncio.get_event_loop()

        def _load_model() -> tuple[Any, Any]:
            """Load model and processor synchronously."""
            # Load processor
            processor = AutoProcessor.from_pretrained(model_path)

            # Determine device and dtype
            if torch.cuda.is_available():
                device = "cuda"
                dtype = torch.float16
            else:
                device = "cpu"
                dtype = torch.float32

            # Load model
            model = VitPoseForPoseEstimation.from_pretrained(
                model_path,
                torch_dtype=dtype,
            )

            # Move to device and set eval mode
            model = model.to(device)
            model.eval()

            return model, processor

        model, processor = await loop.run_in_executor(None, _load_model)

        logger.info(f"Successfully loaded ViTPose model from {model_path}")
        return (model, processor)

    except ImportError as e:
        logger.warning(
            "transformers or torch package not installed. "
            "Install with: pip install transformers torch"
        )
        raise ImportError(
            "ViTPose requires transformers and torch. Install with: pip install transformers torch"
        ) from e

    except Exception as e:
        logger.error(f"Failed to load ViTPose model from {model_path}: {e}")
        raise RuntimeError(f"Failed to load ViTPose model: {e}") from e


def extract_keypoints_from_output(
    outputs: Any,
    processor: Any,
    image_sizes: list[tuple[int, int]],
    min_confidence: float = 0.3,
) -> list[dict[str, Keypoint]]:
    """Extract keypoints from ViTPose model output.

    Args:
        outputs: Raw model outputs from VitPoseForPoseEstimation
        processor: The ViTPose processor for post-processing
        image_sizes: List of (height, width) tuples for each image
        min_confidence: Minimum confidence threshold for keypoints

    Returns:
        List of dictionaries mapping keypoint names to Keypoint objects
    """
    try:
        # Post-process outputs to get keypoint coordinates
        pose_results = processor.post_process_pose_estimation(
            outputs,
            boxes=[[[0, 0, w, h]] for h, w in image_sizes],  # Full image as bbox
        )

        all_keypoints: list[dict[str, Keypoint]] = []

        for result in pose_results:
            if not result:
                all_keypoints.append({})
                continue

            # Get first person's keypoints (for person crops, there's typically one)
            person_result = result[0] if result else None
            if person_result is None:
                all_keypoints.append({})
                continue

            keypoints_tensor = person_result.get("keypoints")
            scores_tensor = person_result.get("scores")

            if keypoints_tensor is None or scores_tensor is None:
                all_keypoints.append({})
                continue

            # Convert to numpy if tensor
            if hasattr(keypoints_tensor, "cpu"):
                keypoints_array = keypoints_tensor.cpu().numpy()
                scores_array = scores_tensor.cpu().numpy()
            else:
                keypoints_array = keypoints_tensor
                scores_array = scores_tensor

            keypoints: dict[str, Keypoint] = {}
            for idx, name in enumerate(KEYPOINT_NAMES):
                if idx < len(keypoints_array) and idx < len(scores_array):
                    confidence = float(scores_array[idx])
                    if confidence >= min_confidence:
                        keypoints[name] = Keypoint(
                            x=float(keypoints_array[idx][0]),
                            y=float(keypoints_array[idx][1]),
                            confidence=confidence,
                            name=name,
                        )

            all_keypoints.append(keypoints)

        return all_keypoints

    except Exception as e:
        logger.error(f"Failed to extract keypoints from output: {e}")
        return []


def classify_pose(keypoints: dict[str, Keypoint]) -> tuple[str, float]:  # noqa: PLR0912
    """Classify pose based on keypoint positions.

    Analyzes the spatial relationships between keypoints to determine
    the overall body pose for security-relevant classification.

    The classification uses relative body proportions to work with both
    normalized (0-1) and pixel coordinate systems.

    Args:
        keypoints: Dictionary mapping keypoint names to Keypoint objects

    Returns:
        Tuple of (pose_class, confidence) where pose_class is one of:
        - "standing": Upright posture
        - "crouching": Bent knees, lowered center of gravity
        - "running": Dynamic motion with leg spread
        - "sitting": Hips below knee level
        - "lying": Horizontal body orientation
        - "unknown": Insufficient keypoint data

    The confidence reflects how well the keypoints match the pose pattern.
    """
    # Check if we have enough keypoints for classification
    required_keypoints = ["left_hip", "right_hip", "left_knee", "right_knee"]
    available = sum(1 for kp in required_keypoints if kp in keypoints)

    if available < 2:
        return ("unknown", 0.0)

    # Get keypoint positions (use available keypoints, averaging left/right)
    def get_avg_y(*names: str) -> float | None:
        values = [keypoints[n].y for n in names if n in keypoints]
        return sum(values) / len(values) if values else None

    def get_avg_x(*names: str) -> float | None:
        values = [keypoints[n].x for n in names if n in keypoints]
        return sum(values) / len(values) if values else None

    hip_y = get_avg_y("left_hip", "right_hip")
    knee_y = get_avg_y("left_knee", "right_knee")
    ankle_y = get_avg_y("left_ankle", "right_ankle")
    shoulder_y = get_avg_y("left_shoulder", "right_shoulder")

    # For horizontal analysis
    shoulder_x = get_avg_x("left_shoulder", "right_shoulder")
    ankle_x = get_avg_x("left_ankle", "right_ankle")

    # Calculate body height for normalization (shoulder to ankle, or hip to ankle)
    body_height = 1.0  # Default
    if shoulder_y is not None and ankle_y is not None:
        body_height = max(abs(ankle_y - shoulder_y), 1.0)
    elif hip_y is not None and ankle_y is not None:
        body_height = max(abs(ankle_y - hip_y) * 1.5, 1.0)  # Estimate full height

    # Calculate hip width for reference
    hip_width = 1.0
    left_hip = keypoints.get("left_hip")
    right_hip = keypoints.get("right_hip")
    if left_hip and right_hip:
        hip_width = max(abs(left_hip.x - right_hip.x), 1.0)

    # Calculate leg spread normalized to hip width
    left_ankle = keypoints.get("left_ankle")
    right_ankle = keypoints.get("right_ankle")
    leg_spread_ratio = 0.0
    if left_ankle and right_ankle:
        leg_spread = abs(left_ankle.x - right_ankle.x)
        leg_spread_ratio = leg_spread / hip_width

    # Check for arm swing (running indicator) - normalized to body height
    left_wrist = keypoints.get("left_wrist")
    right_wrist = keypoints.get("right_wrist")
    left_elbow = keypoints.get("left_elbow")
    right_elbow = keypoints.get("right_elbow")

    arm_asymmetry_ratio = 0.0
    if left_wrist and right_wrist and left_elbow and right_elbow:
        # Check if arms are in different positions (asymmetric = motion)
        arm_asymmetry = abs(left_wrist.y - right_wrist.y)
        arm_asymmetry_ratio = arm_asymmetry / body_height

    # Classification logic with confidence scoring
    pose_scores: dict[str, float] = {
        "standing": 0.0,
        "crouching": 0.0,
        "running": 0.0,
        "sitting": 0.0,
        "lying": 0.0,
    }

    # Check for lying down (horizontal orientation)
    if shoulder_y is not None and hip_y is not None and ankle_y is not None:
        vertical_span = abs(shoulder_y - ankle_y)
        horizontal_span = 0.0
        if shoulder_x is not None and ankle_x is not None:
            horizontal_span = abs(shoulder_x - ankle_x)

        if horizontal_span > vertical_span * 1.5:
            pose_scores["lying"] = 0.8
        elif vertical_span > 0 and horizontal_span / vertical_span > 3.0:
            pose_scores["lying"] = 0.6

    # Check for sitting (hips at or below knee level)
    if hip_y is not None and knee_y is not None:
        # In image coordinates, higher Y means lower position
        # Sitting: hips are at approximately the same Y level as knees
        hip_knee_diff = hip_y - knee_y
        if hip_knee_diff >= 0:  # Hips at or below knees (Y increases down)
            pose_scores["sitting"] = 0.75

    # Check for standing (upright, aligned, feet relatively together)
    # This is checked first as a baseline - other poses may override
    is_vertically_aligned = (
        hip_y is not None
        and knee_y is not None
        and ankle_y is not None
        and hip_y < knee_y < ankle_y
    )
    if is_vertically_aligned and leg_spread_ratio < 2.0:
        pose_scores["standing"] = 0.6
        if shoulder_y is not None and hip_y is not None and shoulder_y < hip_y:
            pose_scores["standing"] = 0.8

    # Check for crouching (bent knees with hips ABOVE knees, but close together)
    # Crouching overrides standing if torso is compressed
    if hip_y is not None and knee_y is not None and shoulder_y is not None and hip_y < knee_y:
        torso_length = abs(hip_y - shoulder_y)
        upper_leg_length = abs(knee_y - hip_y)
        torso_to_upper_leg_ratio = torso_length / max(upper_leg_length, 1.0)
        # Compressed torso indicates crouching - higher score than standing to override
        if torso_to_upper_leg_ratio < 0.8:
            pose_scores["crouching"] = 0.85

    # Check for running (significant leg spread + arm swing)
    # Running requires wide leg spread, optionally with arm asymmetry
    if leg_spread_ratio > 3.0:
        pose_scores["running"] = 0.5 + (0.3 if arm_asymmetry_ratio > 0.15 else 0.0)

    # Select the pose with highest score
    best_pose = max(pose_scores.items(), key=lambda x: x[1])

    if best_pose[1] < 0.3:
        return ("unknown", 0.0)

    return (best_pose[0], best_pose[1])


async def extract_pose_from_crop(
    model: Any,
    processor: Any,
    person_crop: Image.Image,
    bbox: list[float] | None = None,
) -> PoseResult:
    """Extract pose keypoints from a person crop image.

    This is a convenience function for processing a single person crop
    through the ViTPose model and returning classified results.

    Args:
        model: Loaded ViTPose model
        processor: ViTPose processor
        person_crop: PIL Image of cropped person region
        bbox: Optional original bounding box [x1, y1, x2, y2]

    Returns:
        PoseResult with keypoints and classified pose
    """
    try:
        import torch

        # Prepare image for model
        inputs = processor(images=person_crop, return_tensors="pt")

        # Move to same device as model
        device = next(model.parameters()).device
        inputs = {k: v.to(device) for k, v in inputs.items()}

        # Run inference
        with torch.no_grad():
            outputs = model(**inputs)

        # Extract keypoints
        image_size = (person_crop.height, person_crop.width)
        keypoints_list = extract_keypoints_from_output(
            outputs, processor, [image_size], min_confidence=0.3
        )

        keypoints = keypoints_list[0] if keypoints_list else {}

        # Classify pose
        pose_class, pose_confidence = classify_pose(keypoints)

        return PoseResult(
            keypoints=keypoints,
            pose_class=pose_class,
            pose_confidence=pose_confidence,
            bbox=bbox,
        )

    except Exception as e:
        logger.error(f"Failed to extract pose from crop: {e}")
        return PoseResult(
            keypoints={},
            pose_class="unknown",
            pose_confidence=0.0,
            bbox=bbox,
        )


async def extract_poses_batch(
    model: Any,
    processor: Any,
    person_crops: list[Image.Image],
    bboxes: list[list[float]] | None = None,
) -> list[PoseResult]:
    """Extract poses from multiple person crops in batch.

    Args:
        model: Loaded ViTPose model
        processor: ViTPose processor
        person_crops: List of PIL Images of cropped person regions
        bboxes: Optional list of bounding boxes corresponding to crops

    Returns:
        List of PoseResult objects for each input crop
    """
    if not person_crops:
        return []

    if bboxes is None:
        bboxes = [None] * len(person_crops)  # type: ignore[list-item]

    try:
        import torch

        # Prepare batch
        inputs = processor(images=person_crops, return_tensors="pt")

        # Move to same device as model
        device = next(model.parameters()).device
        inputs = {k: v.to(device) for k, v in inputs.items()}

        # Run inference
        with torch.no_grad():
            outputs = model(**inputs)

        # Extract keypoints for all images
        image_sizes = [(img.height, img.width) for img in person_crops]
        keypoints_list = extract_keypoints_from_output(
            outputs, processor, image_sizes, min_confidence=0.3
        )

        # Build results
        results: list[PoseResult] = []
        for i, keypoints in enumerate(keypoints_list):
            pose_class, pose_confidence = classify_pose(keypoints)
            results.append(
                PoseResult(
                    keypoints=keypoints,
                    pose_class=pose_class,
                    pose_confidence=pose_confidence,
                    bbox=bboxes[i] if i < len(bboxes) else None,
                )
            )

        return results

    except Exception as e:
        logger.error(f"Failed to extract poses from batch: {e}")
        # Return empty results for each crop
        return [
            PoseResult(
                keypoints={},
                pose_class="unknown",
                pose_confidence=0.0,
                bbox=bboxes[i] if i < len(bboxes) else None,
            )
            for i in range(len(person_crops))
        ]
