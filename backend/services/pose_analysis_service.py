"""Pose analysis service for security alert detection and data transformation.

This module provides services for analyzing pose estimation results to:
1. Convert PoseResult keypoints from named dict format to COCO array format
2. Detect security-relevant alerts from keypoint patterns
3. Return structured pose enrichment data matching frontend expectations

Security Alerts Detected:
    - crouching: Person in crouching position (hips low, knees bent)
    - lying_down: Person in horizontal/prone position
    - hands_raised: Both wrists positioned above shoulders
    - fighting_stance: Asymmetric wide leg spread indicating aggressive posture

Output Format:
    The service returns a structured dict with:
    - posture: Classified posture type (standing, walking, running, sitting, crouching, lying_down)
    - alerts: List of security-relevant alerts
    - security_alerts: Alias for alerts (backward compatibility)
    - keypoints: COCO 17 keypoint format [[x, y, conf], ...]
    - keypoint_count: Number of valid keypoints with non-zero confidence
    - confidence: Overall pose classification confidence
"""

from __future__ import annotations

from typing import Any

from backend.core.logging import get_logger
from backend.services.vitpose_loader import KEYPOINT_NAMES, Keypoint, PoseResult

logger = get_logger(__name__)

# Confidence threshold for considering a keypoint valid in alert detection
ALERT_CONFIDENCE_THRESHOLD = 0.3

# Posture type mapping from PoseResult classifications
POSTURE_MAP: dict[str, str] = {
    "standing": "standing",
    "walking": "walking",
    "running": "running",
    "sitting": "sitting",
    "crouching": "crouching",
    "lying": "lying_down",  # Map 'lying' to 'lying_down' for consistency
    "unknown": "unknown",
}


def keypoints_to_coco_array(keypoints: dict[str, Keypoint]) -> list[list[float]]:
    """Convert keypoints dict to COCO 17 keypoint array format.

    Converts from the named dictionary format returned by ViTPose loader
    to the standard COCO array format expected by the frontend for
    skeleton overlay rendering.

    Args:
        keypoints: Dictionary mapping keypoint names to Keypoint objects.
                  Missing keypoints will be filled with [0.0, 0.0, 0.0].

    Returns:
        List of 17 keypoints in COCO order, each as [x, y, confidence].
        The order follows COCO keypoint indices:
        0: nose, 1: left_eye, 2: right_eye, 3: left_ear, 4: right_ear,
        5: left_shoulder, 6: right_shoulder, 7: left_elbow, 8: right_elbow,
        9: left_wrist, 10: right_wrist, 11: left_hip, 12: right_hip,
        13: left_knee, 14: right_knee, 15: left_ankle, 16: right_ankle

    Example:
        >>> kps = {"nose": Keypoint(x=100.0, y=50.0, confidence=0.95, name="nose")}
        >>> result = keypoints_to_coco_array(kps)
        >>> result[0]  # nose at index 0
        [100.0, 50.0, 0.95]
        >>> result[1]  # left_eye missing
        [0.0, 0.0, 0.0]
    """
    coco_array: list[list[float]] = []

    for name in KEYPOINT_NAMES:
        kp = keypoints.get(name)
        if kp is not None:
            coco_array.append([kp.x, kp.y, kp.confidence])
        else:
            # Missing keypoint - add placeholder with zero confidence
            coco_array.append([0.0, 0.0, 0.0])

    return coco_array


def count_valid_keypoints(keypoints: dict[str, Keypoint]) -> int:
    """Count keypoints with non-zero confidence.

    Args:
        keypoints: Dictionary mapping keypoint names to Keypoint objects.

    Returns:
        Number of keypoints with confidence > 0.
    """
    return sum(1 for kp in keypoints.values() if kp.confidence > 0)


def _get_keypoint_if_confident(
    keypoints: dict[str, Keypoint],
    name: str,
    threshold: float = ALERT_CONFIDENCE_THRESHOLD,
) -> Keypoint | None:
    """Get a keypoint if it exists and meets confidence threshold.

    Args:
        keypoints: Dictionary mapping keypoint names to Keypoint objects.
        name: Name of the keypoint to retrieve.
        threshold: Minimum confidence threshold.

    Returns:
        Keypoint if found and confidence >= threshold, None otherwise.
    """
    kp = keypoints.get(name)
    if kp is not None and kp.confidence >= threshold:
        return kp
    return None


def detect_crouching(keypoints: dict[str, Keypoint]) -> bool:
    """Detect if person is in a crouching position.

    Crouching is detected when hips are lowered relative to normal standing,
    with knees bent. This is a security-relevant posture that may indicate
    someone hiding or preparing for sudden movement.

    Detection criteria:
    - Both hips and at least one knee must be detected with sufficient confidence
    - Torso (shoulder-to-hip) is compressed relative to upper leg length
    - Alternative: hip-knee vertical distance is small relative to body proportions

    Args:
        keypoints: Dictionary mapping keypoint names to Keypoint objects.

    Returns:
        True if crouching posture detected, False otherwise.
    """
    # Get hip keypoints
    left_hip = _get_keypoint_if_confident(keypoints, "left_hip")
    right_hip = _get_keypoint_if_confident(keypoints, "right_hip")

    if not left_hip and not right_hip:
        return False

    # Get knee keypoints
    left_knee = _get_keypoint_if_confident(keypoints, "left_knee")
    right_knee = _get_keypoint_if_confident(keypoints, "right_knee")

    if not left_knee and not right_knee:
        return False

    # Get shoulder keypoints for torso compression check
    left_shoulder = _get_keypoint_if_confident(keypoints, "left_shoulder")
    right_shoulder = _get_keypoint_if_confident(keypoints, "right_shoulder")

    # Calculate average positions
    hip_y = 0.0
    hip_count = 0
    if left_hip:
        hip_y += left_hip.y
        hip_count += 1
    if right_hip:
        hip_y += right_hip.y
        hip_count += 1
    hip_y /= max(hip_count, 1)

    knee_y = 0.0
    knee_count = 0
    if left_knee:
        knee_y += left_knee.y
        knee_count += 1
    if right_knee:
        knee_y += right_knee.y
        knee_count += 1
    knee_y /= max(knee_count, 1)

    # Check if we have shoulders for torso compression check
    if left_shoulder or right_shoulder:
        shoulder_y = 0.0
        shoulder_count = 0
        if left_shoulder:
            shoulder_y += left_shoulder.y
            shoulder_count += 1
        if right_shoulder:
            shoulder_y += right_shoulder.y
            shoulder_count += 1
        shoulder_y /= max(shoulder_count, 1)

        # In image coordinates, Y increases downward
        # Crouching: hips above knees (hip_y < knee_y) but torso compressed
        if hip_y < knee_y:  # Hips are above knees
            torso_length = abs(hip_y - shoulder_y)
            upper_leg_length = abs(knee_y - hip_y)

            # Compressed torso indicates crouching
            if upper_leg_length > 0:
                torso_to_leg_ratio = torso_length / upper_leg_length
                # Ratio < 0.8 indicates compressed torso (crouching)
                return torso_to_leg_ratio < 0.8

    # Fallback: Check if hip-knee distance is very small (deep crouch)
    hip_knee_distance = abs(knee_y - hip_y)
    return hip_knee_distance < 20  # Very close = deep crouch


def detect_lying_down(keypoints: dict[str, Keypoint]) -> bool:
    """Detect if person is lying down (horizontal orientation).

    Lying down is detected when the body has a predominantly horizontal
    orientation. This is security-relevant as it may indicate someone
    who has fallen, is hiding, or is unconscious.

    Detection criteria:
    - Horizontal span (shoulder to ankle X distance) >> vertical span (Y distance)
    - Body alignment is more horizontal than vertical

    Args:
        keypoints: Dictionary mapping keypoint names to Keypoint objects.

    Returns:
        True if lying down posture detected, False otherwise.
    """
    # Get shoulder keypoints
    left_shoulder = _get_keypoint_if_confident(keypoints, "left_shoulder")
    right_shoulder = _get_keypoint_if_confident(keypoints, "right_shoulder")

    # Get ankle keypoints
    left_ankle = _get_keypoint_if_confident(keypoints, "left_ankle")
    right_ankle = _get_keypoint_if_confident(keypoints, "right_ankle")

    # Need at least one shoulder and one ankle
    if not (left_shoulder or right_shoulder) or not (left_ankle or right_ankle):
        return False

    # Calculate average positions
    shoulder_x = 0.0
    shoulder_y = 0.0
    shoulder_count = 0
    if left_shoulder:
        shoulder_x += left_shoulder.x
        shoulder_y += left_shoulder.y
        shoulder_count += 1
    if right_shoulder:
        shoulder_x += right_shoulder.x
        shoulder_y += right_shoulder.y
        shoulder_count += 1
    shoulder_x /= max(shoulder_count, 1)
    shoulder_y /= max(shoulder_count, 1)

    ankle_x = 0.0
    ankle_y = 0.0
    ankle_count = 0
    if left_ankle:
        ankle_x += left_ankle.x
        ankle_y += left_ankle.y
        ankle_count += 1
    if right_ankle:
        ankle_x += right_ankle.x
        ankle_y += right_ankle.y
        ankle_count += 1
    ankle_x /= max(ankle_count, 1)
    ankle_y /= max(ankle_count, 1)

    # Calculate spans
    horizontal_span = abs(shoulder_x - ankle_x)
    vertical_span = abs(shoulder_y - ankle_y)

    # Lying down if horizontal span is significantly larger than vertical
    # Using 1.5x threshold as per vitpose_loader.py classify_pose
    if vertical_span > 0:
        return horizontal_span > vertical_span * 1.5

    # If vertical_span is 0, check if there's significant horizontal span
    return horizontal_span > 50  # Threshold in pixels


def detect_hands_raised(keypoints: dict[str, Keypoint]) -> bool:
    """Detect if both hands are raised above shoulders.

    Hands raised is detected when both wrists are positioned above
    the shoulder line. This is security-relevant as it may indicate
    surrender, signaling, or threatening gestures.

    Detection criteria:
    - Both wrists must be detected with sufficient confidence
    - Both wrists Y coordinate must be less than shoulder Y (higher in image)

    Args:
        keypoints: Dictionary mapping keypoint names to Keypoint objects.

    Returns:
        True if hands raised posture detected, False otherwise.
    """
    # Get wrist keypoints - need both for "hands raised"
    left_wrist = _get_keypoint_if_confident(keypoints, "left_wrist")
    right_wrist = _get_keypoint_if_confident(keypoints, "right_wrist")

    if not left_wrist or not right_wrist:
        return False

    # Get shoulder keypoints
    left_shoulder = _get_keypoint_if_confident(keypoints, "left_shoulder")
    right_shoulder = _get_keypoint_if_confident(keypoints, "right_shoulder")

    if not left_shoulder and not right_shoulder:
        return False

    # Calculate average shoulder Y position
    shoulder_y = 0.0
    shoulder_count = 0
    if left_shoulder:
        shoulder_y += left_shoulder.y
        shoulder_count += 1
    if right_shoulder:
        shoulder_y += right_shoulder.y
        shoulder_count += 1
    shoulder_y /= max(shoulder_count, 1)

    # In image coordinates, Y increases downward
    # Wrists above shoulders means wrist_y < shoulder_y
    # Add small margin (10 pixels) to avoid false positives from noise
    margin = 10.0
    left_above = left_wrist.y < (shoulder_y - margin)
    right_above = right_wrist.y < (shoulder_y - margin)

    return left_above and right_above


def detect_fighting_stance(keypoints: dict[str, Keypoint]) -> bool:
    """Detect if person is in a fighting stance.

    Fighting stance is detected when there's an asymmetric wide leg spread,
    indicating an aggressive or defensive posture. This is security-relevant
    as it may indicate preparation for physical confrontation.

    Detection criteria:
    - Wide leg spread (ankles far apart relative to hip width)
    - Asymmetric positioning (one foot forward/back)
    - Arms may show defensive positioning

    Args:
        keypoints: Dictionary mapping keypoint names to Keypoint objects.

    Returns:
        True if fighting stance detected, False otherwise.
    """
    # Get hip keypoints for reference width
    left_hip = _get_keypoint_if_confident(keypoints, "left_hip")
    right_hip = _get_keypoint_if_confident(keypoints, "right_hip")

    if not left_hip or not right_hip:
        return False

    # Get ankle keypoints
    left_ankle = _get_keypoint_if_confident(keypoints, "left_ankle")
    right_ankle = _get_keypoint_if_confident(keypoints, "right_ankle")

    if not left_ankle or not right_ankle:
        return False

    # Calculate hip width
    hip_width = abs(left_hip.x - right_hip.x)
    if hip_width < 1:  # Avoid division by zero
        hip_width = 1.0

    # Calculate leg spread in X and Y directions
    ankle_x_spread = abs(left_ankle.x - right_ankle.x)
    ankle_y_spread = abs(left_ankle.y - right_ankle.y)

    # Calculate leg spread ratio relative to hip width
    leg_spread_ratio = ankle_x_spread / hip_width

    # Fighting stance characteristics:
    # 1. Wide lateral spread (legs spread wider than normal standing)
    # 2. Asymmetric Y position (one foot forward/back, creating depth)
    # 3. Not as extreme as running (which has leg_spread_ratio > 3.0)

    # Wide stance but not running level (2.0 to 4.0 range)
    is_wide_stance = 2.0 < leg_spread_ratio < 4.0

    # Asymmetric Y indicates staggered feet (front/back positioning)
    # Typical fighting stance has significant Y offset between feet
    is_asymmetric = ankle_y_spread > (hip_width * 0.5)

    # Fighting stance requires both wide and asymmetric
    return is_wide_stance and is_asymmetric


def detect_security_alerts(keypoints: dict[str, Keypoint], posture: str) -> list[str]:
    """Detect all security-relevant alerts from keypoint patterns.

    Analyzes the keypoint positions to identify security-relevant
    postures and behaviors.

    Args:
        keypoints: Dictionary mapping keypoint names to Keypoint objects.
        posture: The classified posture type from pose estimation.

    Returns:
        List of detected security alert strings.
    """
    alerts: list[str] = []

    # Check each alert type
    # Note: crouching and lying_down are also captured in posture,
    # but we detect them independently for consistency

    if detect_crouching(keypoints) or posture == "crouching":
        alerts.append("crouching")

    if detect_lying_down(keypoints) or posture in ("lying", "lying_down"):
        alerts.append("lying_down")

    if detect_hands_raised(keypoints):
        alerts.append("hands_raised")

    if detect_fighting_stance(keypoints):
        alerts.append("fighting_stance")

    return alerts


def normalize_posture(pose_class: str) -> str:
    """Normalize pose classification to standard posture type.

    Maps the pose classification from vitpose_loader to the
    standardized posture types expected by the frontend.

    Args:
        pose_class: Pose class from PoseResult (e.g., "lying", "standing").

    Returns:
        Normalized posture string (e.g., "lying_down", "standing").
    """
    return POSTURE_MAP.get(pose_class, "unknown")


def analyze_pose(pose_result: PoseResult) -> dict[str, Any]:
    """Analyze a PoseResult and return structured enrichment data.

    Main entry point for pose analysis. Takes a PoseResult from
    ViTPose estimation and returns a structured dictionary suitable
    for frontend consumption and database storage.

    Args:
        pose_result: PoseResult from vitpose_loader with keypoints
                    and pose classification.

    Returns:
        Dictionary with pose enrichment data:
        - posture: Normalized posture type string
        - alerts: List of security alert strings
        - security_alerts: Alias for alerts (backward compatibility)
        - keypoints: COCO 17 keypoint array [[x, y, conf], ...]
        - keypoint_count: Number of valid keypoints
        - confidence: Pose classification confidence

    Example:
        >>> from backend.services.vitpose_loader import PoseResult, Keypoint
        >>> pose = PoseResult(
        ...     keypoints={"nose": Keypoint(100, 50, 0.95, "nose")},
        ...     pose_class="standing",
        ...     pose_confidence=0.85
        ... )
        >>> result = analyze_pose(pose)
        >>> result["posture"]
        'standing'
        >>> result["keypoint_count"]
        1
    """
    keypoints = pose_result.keypoints
    pose_class = pose_result.pose_class
    pose_confidence = pose_result.pose_confidence

    # Normalize posture type
    posture = normalize_posture(pose_class)

    # Convert keypoints to COCO array format
    keypoints_array = keypoints_to_coco_array(keypoints)

    # Count valid keypoints
    keypoint_count = count_valid_keypoints(keypoints)

    # Detect security alerts
    alerts = detect_security_alerts(keypoints, posture)

    return {
        "posture": posture,
        "alerts": alerts,
        "security_alerts": alerts,  # Backward compatibility alias
        "keypoints": keypoints_array,
        "keypoint_count": keypoint_count,
        "confidence": pose_confidence,
    }


def analyze_poses_batch(
    pose_results: dict[str, PoseResult],
) -> dict[str, dict[str, Any]]:
    """Analyze multiple PoseResults and return structured enrichment data.

    Batch processing entry point for analyzing multiple pose results,
    typically one per detected person in an image.

    Args:
        pose_results: Dictionary mapping detection IDs to PoseResult objects.

    Returns:
        Dictionary mapping detection IDs to pose enrichment data dicts.

    Example:
        >>> poses = {"0": pose_result_1, "1": pose_result_2}
        >>> results = analyze_poses_batch(poses)
        >>> results["0"]["posture"]
        'standing'
    """
    return {det_id: analyze_pose(pose_result) for det_id, pose_result in pose_results.items()}


def create_empty_pose_enrichment() -> dict[str, Any]:
    """Create an empty pose enrichment result.

    Used when pose estimation is not available or failed.

    Returns:
        Dictionary with empty/default pose enrichment data.
    """
    return {
        "posture": "unknown",
        "alerts": [],
        "security_alerts": [],
        "keypoints": [[0.0, 0.0, 0.0] for _ in range(17)],
        "keypoint_count": 0,
        "confidence": 0.0,
    }
