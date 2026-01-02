"""ViTPose+ Small Human Pose Estimation Module.

This module provides the PoseAnalyzer class for human pose keypoint detection
using the ViTPose+ Small model from HuggingFace.

Features:
- Detects 17 COCO keypoints (nose, eyes, ears, shoulders, elbows, wrists, hips, knees, ankles)
- Classifies posture (standing, walking, sitting, crouching, lying_down, running)
- Generates security-relevant alerts (crouching, lying_down, hands_raised, fighting_stance)

Reference: https://huggingface.co/usyd-community/vitpose-plus-small
"""

import logging
from typing import Any

import torch
from PIL import Image

logger = logging.getLogger(__name__)

# COCO 17 keypoint names
COCO_KEYPOINT_NAMES: list[str] = [
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

# Posture classification labels
POSTURE_LABELS: list[str] = [
    "standing",
    "walking",
    "sitting",
    "crouching",
    "lying_down",
    "running",
]

# Security-relevant alert conditions based on posture
POSE_ALERT_CONDITIONS: dict[str, str] = {
    "crouching": "crouching",  # Potential hiding/break-in
    "lying_down": "lying_down",  # Fallen person, medical emergency
}


class PoseAnalyzer:
    """ViTPose+ Small human pose estimation model wrapper.

    Detects 17 COCO keypoints and classifies posture for security analysis.
    Generates security-relevant alerts for suspicious poses.
    """

    def __init__(self, model_path: str, device: str = "cuda:0"):
        """Initialize pose analyzer.

        Args:
            model_path: Path to ViTPose model directory (HuggingFace format)
            device: Device to run inference on
        """
        self.model_path = model_path
        self.device = device
        self.model: Any = None
        self.processor: Any = None

        logger.info(f"Initializing PoseAnalyzer from {self.model_path}")

    def load_model(self) -> None:
        """Load the ViTPose+ Small model."""
        from transformers import AutoProcessor, VitPoseForPoseEstimation

        logger.info("Loading ViTPose+ Small model...")

        self.processor = AutoProcessor.from_pretrained(self.model_path)
        self.model = VitPoseForPoseEstimation.from_pretrained(self.model_path)

        # Move to device
        if "cuda" in self.device and torch.cuda.is_available():
            self.model = self.model.to(self.device).half()  # Use fp16 for efficiency
            logger.info(f"PoseAnalyzer loaded on {self.device} with fp16")
        else:
            self.device = "cpu"
            logger.info("PoseAnalyzer using CPU")

        self.model.eval()
        logger.info("PoseAnalyzer loaded successfully")

    def analyze(
        self,
        image: Image.Image,
        min_confidence: float = 0.3,
    ) -> dict[str, Any]:
        """Analyze pose keypoints from a person crop image.

        Args:
            image: PIL Image of person crop
            min_confidence: Minimum confidence threshold for keypoints

        Returns:
            Dictionary with keypoints, posture, alerts
        """
        if self.model is None or self.processor is None:
            raise RuntimeError("Model not loaded")

        # Ensure RGB mode
        rgb_image = image.convert("RGB") if image.mode != "RGB" else image

        # Prepare image for model
        inputs = self.processor(images=rgb_image, return_tensors="pt")

        # Move to device with correct dtype
        model_dtype = next(self.model.parameters()).dtype
        inputs = {k: v.to(self.device, model_dtype) for k, v in inputs.items()}

        # Run inference
        with torch.no_grad():
            outputs = self.model(**inputs)

        # Post-process to get keypoint coordinates
        image_size = (rgb_image.height, rgb_image.width)
        pose_results = self.processor.post_process_pose_estimation(
            outputs,
            boxes=[[[0, 0, image_size[1], image_size[0]]]],  # Full image as bbox
        )

        # Extract keypoints
        keypoints: list[dict[str, Any]] = []
        if pose_results and pose_results[0]:
            person_result = pose_results[0][0] if pose_results[0] else None
            if person_result is not None:
                keypoints_tensor = person_result.get("keypoints")
                scores_tensor = person_result.get("scores")

                if keypoints_tensor is not None and scores_tensor is not None:
                    # Convert to numpy if tensor
                    if hasattr(keypoints_tensor, "cpu"):
                        keypoints_array = keypoints_tensor.cpu().numpy()
                        scores_array = scores_tensor.cpu().numpy()
                    else:
                        keypoints_array = keypoints_tensor
                        scores_array = scores_tensor

                    for idx, name in enumerate(COCO_KEYPOINT_NAMES):
                        if idx < len(keypoints_array) and idx < len(scores_array):
                            confidence = float(scores_array[idx])
                            if confidence >= min_confidence:
                                # Normalize coordinates to 0-1 range
                                x_norm = float(keypoints_array[idx][0]) / image_size[1]
                                y_norm = float(keypoints_array[idx][1]) / image_size[0]
                                keypoints.append(
                                    {
                                        "name": name,
                                        "x": round(x_norm, 4),
                                        "y": round(y_norm, 4),
                                        "confidence": round(confidence, 4),
                                    }
                                )

        # Classify posture
        posture = self._classify_posture(keypoints)

        # Generate alerts
        alerts = self._generate_alerts(posture, keypoints)

        return {
            "keypoints": keypoints,
            "posture": posture,
            "alerts": alerts,
        }

    def _get_avg_coord(
        self,
        kp_dict: dict[str, dict[str, float]],
        names: tuple[str, ...],
        coord: str,
    ) -> float | None:
        """Get average coordinate value for specified keypoints."""
        values = [kp_dict[n][coord] for n in names if n in kp_dict]
        return sum(values) / len(values) if values else None

    def _compute_body_metrics(
        self,
        kp_dict: dict[str, dict[str, float]],
    ) -> dict[str, float]:
        """Compute body metrics for posture classification."""
        hip_y = self._get_avg_coord(kp_dict, ("left_hip", "right_hip"), "y")
        knee_y = self._get_avg_coord(kp_dict, ("left_knee", "right_knee"), "y")
        ankle_y = self._get_avg_coord(kp_dict, ("left_ankle", "right_ankle"), "y")
        shoulder_y = self._get_avg_coord(kp_dict, ("left_shoulder", "right_shoulder"), "y")
        shoulder_x = self._get_avg_coord(kp_dict, ("left_shoulder", "right_shoulder"), "x")
        ankle_x = self._get_avg_coord(kp_dict, ("left_ankle", "right_ankle"), "x")

        # Calculate body height
        body_height = 1.0
        if shoulder_y is not None and ankle_y is not None:
            body_height = max(abs(ankle_y - shoulder_y), 0.01)
        elif hip_y is not None and ankle_y is not None:
            body_height = max(abs(ankle_y - hip_y) * 1.5, 0.01)

        # Calculate hip width
        hip_width = 0.1
        left_hip = kp_dict.get("left_hip")
        right_hip = kp_dict.get("right_hip")
        if left_hip and right_hip:
            hip_width = max(abs(left_hip["x"] - right_hip["x"]), 0.01)

        # Calculate leg spread ratio
        left_ankle = kp_dict.get("left_ankle")
        right_ankle = kp_dict.get("right_ankle")
        leg_spread_ratio = 0.0
        if left_ankle and right_ankle:
            leg_spread = abs(left_ankle["x"] - right_ankle["x"])
            leg_spread_ratio = leg_spread / hip_width

        # Calculate arm asymmetry ratio
        left_wrist = kp_dict.get("left_wrist")
        right_wrist = kp_dict.get("right_wrist")
        arm_asymmetry_ratio = 0.0
        if left_wrist and right_wrist:
            arm_asymmetry = abs(left_wrist["y"] - right_wrist["y"])
            arm_asymmetry_ratio = arm_asymmetry / body_height

        return {
            "hip_y": hip_y if hip_y is not None else -1.0,
            "knee_y": knee_y if knee_y is not None else -1.0,
            "ankle_y": ankle_y if ankle_y is not None else -1.0,
            "shoulder_y": shoulder_y if shoulder_y is not None else -1.0,
            "shoulder_x": shoulder_x if shoulder_x is not None else -1.0,
            "ankle_x": ankle_x if ankle_x is not None else -1.0,
            "leg_spread_ratio": leg_spread_ratio,
            "arm_asymmetry_ratio": arm_asymmetry_ratio,
            "has_hip_y": hip_y is not None,
            "has_knee_y": knee_y is not None,
            "has_ankle_y": ankle_y is not None,
            "has_shoulder_y": shoulder_y is not None,
            "has_shoulder_x": shoulder_x is not None,
            "has_ankle_x": ankle_x is not None,
        }

    def _score_postures(self, metrics: dict[str, float]) -> dict[str, float]:
        """Score each posture based on body metrics."""
        scores: dict[str, float] = {
            "standing": 0.0,
            "walking": 0.0,
            "sitting": 0.0,
            "crouching": 0.0,
            "lying_down": 0.0,
            "running": 0.0,
        }

        hip_y = metrics["hip_y"] if metrics["has_hip_y"] else None
        knee_y = metrics["knee_y"] if metrics["has_knee_y"] else None
        ankle_y = metrics["ankle_y"] if metrics["has_ankle_y"] else None
        shoulder_y = metrics["shoulder_y"] if metrics["has_shoulder_y"] else None
        shoulder_x = metrics["shoulder_x"] if metrics["has_shoulder_x"] else None
        ankle_x = metrics["ankle_x"] if metrics["has_ankle_x"] else None
        leg_spread_ratio = metrics["leg_spread_ratio"]
        arm_asymmetry_ratio = metrics["arm_asymmetry_ratio"]

        # Lying down: horizontal orientation
        if shoulder_y is not None and hip_y is not None and ankle_y is not None:
            vertical_span = abs(shoulder_y - ankle_y)
            horizontal_span = abs(shoulder_x - ankle_x) if shoulder_x and ankle_x else 0.0
            if horizontal_span > vertical_span * 1.5:
                scores["lying_down"] = 0.8

        # Sitting: hips at or below knee level
        if hip_y is not None and knee_y is not None and hip_y - knee_y >= 0:
            scores["sitting"] = 0.75

        # Standing: upright, aligned
        is_aligned = (
            hip_y is not None
            and knee_y is not None
            and ankle_y is not None
            and hip_y < knee_y < ankle_y
        )
        if is_aligned and leg_spread_ratio < 2.0:
            scores["standing"] = 0.6
            if shoulder_y is not None and hip_y is not None and shoulder_y < hip_y:
                scores["standing"] = 0.8

        # Crouching: compressed torso
        if hip_y is not None and knee_y is not None and shoulder_y is not None and hip_y < knee_y:
            torso_length = abs(hip_y - shoulder_y)
            upper_leg_length = abs(knee_y - hip_y)
            if torso_length / max(upper_leg_length, 0.01) < 0.8:
                scores["crouching"] = 0.85

        # Walking: moderate leg spread
        if 1.5 < leg_spread_ratio <= 3.0:
            scores["walking"] = 0.5 + (0.2 if arm_asymmetry_ratio > 0.1 else 0.0)

        # Running: wide leg spread + arm swing
        if leg_spread_ratio > 3.0:
            scores["running"] = 0.5 + (0.3 if arm_asymmetry_ratio > 0.15 else 0.0)

        return scores

    def _classify_posture(
        self,
        keypoints: list[dict[str, Any]],
    ) -> str:
        """Classify posture from keypoint positions.

        Args:
            keypoints: List of detected keypoints with normalized coordinates

        Returns:
            Posture classification string
        """
        kp_dict: dict[str, dict[str, float]] = {kp["name"]: kp for kp in keypoints}

        # Check if we have enough keypoints
        required = ["left_hip", "right_hip", "left_knee", "right_knee"]
        if sum(1 for kp in required if kp in kp_dict) < 2:
            return "unknown"

        metrics = self._compute_body_metrics(kp_dict)
        pose_scores = self._score_postures(metrics)

        best_pose = max(pose_scores.items(), key=lambda x: x[1])
        return best_pose[0] if best_pose[1] >= 0.3 else "unknown"

    def _generate_alerts(
        self,
        posture: str,
        keypoints: list[dict[str, Any]],
    ) -> list[str]:
        """Generate security-relevant alerts based on pose analysis.

        Args:
            posture: Classified posture
            keypoints: List of detected keypoints

        Returns:
            List of alert strings
        """
        alerts: list[str] = []

        # Check posture-based alerts
        if posture in POSE_ALERT_CONDITIONS:
            alerts.append(POSE_ALERT_CONDITIONS[posture])

        # Additional pose analysis for security alerts
        kp_dict: dict[str, dict[str, float]] = {kp["name"]: kp for kp in keypoints}

        # Check for "hands raised" (potential surrender, robbery)
        left_wrist = kp_dict.get("left_wrist")
        right_wrist = kp_dict.get("right_wrist")
        nose = kp_dict.get("nose")

        if (
            left_wrist
            and right_wrist
            and nose
            and left_wrist["y"] < nose["y"]
            and right_wrist["y"] < nose["y"]
        ):
            # Both wrists above head level (nose)
            alerts.append("hands_raised")

        # Check for "fighting stance" (aggressive posture)
        # Wide stance with arms forward
        left_elbow = kp_dict.get("left_elbow")
        right_elbow = kp_dict.get("right_elbow")
        left_shoulder = kp_dict.get("left_shoulder")
        right_shoulder = kp_dict.get("right_shoulder")
        if left_wrist and right_wrist and left_elbow and right_elbow:
            # Check if arms are extended forward (wrists far from body center)
            left_hip = kp_dict.get("left_hip")
            right_hip = kp_dict.get("right_hip")
            if left_hip and right_hip:
                body_center_x = (left_hip["x"] + right_hip["x"]) / 2
                left_arm_extension = abs(left_wrist["x"] - body_center_x)
                right_arm_extension = abs(right_wrist["x"] - body_center_x)

                # If arms are extended forward with bent elbows (fighting stance)
                # Combined conditions: arms extended, elbows bent, standing posture
                is_fighting_stance = (
                    left_arm_extension > 0.3
                    and right_arm_extension > 0.3
                    and left_shoulder
                    and right_shoulder
                    and left_elbow["y"] > left_shoulder.get("y", 0)
                    and right_elbow["y"] > right_shoulder.get("y", 0)
                    and left_wrist
                    and left_shoulder["y"] < left_elbow["y"] < left_wrist["y"]
                    and posture not in ["sitting", "lying_down"]
                )
                if is_fighting_stance:
                    alerts.append("fighting_stance")

        return alerts
