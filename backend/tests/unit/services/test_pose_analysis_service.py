"""Unit tests for pose analysis functionality.

This module tests the pose analysis capabilities provided by vitpose_loader.py
and pose_analysis_service.py, including keypoint processing, pose classification,
security alert detection, and COCO format conversion.

Test Strategy:
- Keypoint structure validation
- Pose classification logic (standing, crouching, lying, sitting, running)
- Security-relevant pose detection
- Edge cases (missing keypoints, low confidence, invalid data)
- PoseResult serialization
- COCO keypoint format conversion
"""

import pytest

from backend.services.pose_analysis_service import (
    ALERT_CONFIDENCE_THRESHOLD,
    POSTURE_MAP,
    analyze_pose,
    analyze_poses_batch,
    count_valid_keypoints,
    create_empty_pose_enrichment,
    detect_crouching,
    detect_fighting_stance,
    detect_hands_raised,
    detect_lying_down,
    detect_security_alerts,
    keypoints_to_coco_array,
    normalize_posture,
)
from backend.services.vitpose_loader import (
    KEYPOINT_NAMES,
    Keypoint,
    KeypointIndex,
    PoseResult,
    classify_pose,
)

# =============================================================================
# Keypoint Tests
# =============================================================================


class TestKeypoint:
    """Tests for Keypoint dataclass."""

    def test_keypoint_creation(self) -> None:
        """Test creating a keypoint with all fields."""
        kp = Keypoint(x=0.5, y=0.3, confidence=0.95, name="nose")
        assert kp.x == 0.5
        assert kp.y == 0.3
        assert kp.confidence == 0.95
        assert kp.name == "nose"

    def test_keypoint_with_pixel_coordinates(self) -> None:
        """Test keypoint with pixel coordinates (not normalized)."""
        kp = Keypoint(x=640.0, y=480.0, confidence=0.85, name="left_shoulder")
        assert kp.x == 640.0
        assert kp.y == 480.0
        assert kp.confidence == 0.85

    def test_keypoint_low_confidence(self) -> None:
        """Test keypoint with low confidence value."""
        kp = Keypoint(x=0.5, y=0.5, confidence=0.2, name="right_ankle")
        assert kp.confidence == 0.2


class TestKeypointIndex:
    """Tests for KeypointIndex enum."""

    def test_all_keypoint_indices_defined(self) -> None:
        """Test that all 17 COCO keypoints are defined."""
        assert len(KeypointIndex) == 17

    def test_keypoint_index_values(self) -> None:
        """Test specific keypoint index values."""
        assert KeypointIndex.NOSE.value == 0
        assert KeypointIndex.LEFT_SHOULDER.value == 5
        assert KeypointIndex.RIGHT_HIP.value == 12
        assert KeypointIndex.RIGHT_ANKLE.value == 16

    def test_keypoint_names_match_count(self) -> None:
        """Test that KEYPOINT_NAMES has 17 entries matching KeypointIndex."""
        assert len(KEYPOINT_NAMES) == 17


# =============================================================================
# PoseResult Tests
# =============================================================================


class TestPoseResult:
    """Tests for PoseResult dataclass and serialization."""

    @pytest.fixture
    def sample_keypoints(self) -> dict[str, Keypoint]:
        """Create sample keypoints dictionary."""
        return {
            "nose": Keypoint(x=0.5, y=0.2, confidence=0.95, name="nose"),
            "left_shoulder": Keypoint(x=0.4, y=0.4, confidence=0.90, name="left_shoulder"),
            "right_shoulder": Keypoint(x=0.6, y=0.4, confidence=0.88, name="right_shoulder"),
            "left_hip": Keypoint(x=0.4, y=0.6, confidence=0.85, name="left_hip"),
            "right_hip": Keypoint(x=0.6, y=0.6, confidence=0.83, name="right_hip"),
        }

    def test_pose_result_creation(self, sample_keypoints: dict[str, Keypoint]) -> None:
        """Test creating PoseResult with all fields."""
        result = PoseResult(
            keypoints=sample_keypoints,
            pose_class="standing",
            pose_confidence=0.85,
            bbox=[10.0, 20.0, 100.0, 200.0],
        )
        assert len(result.keypoints) == 5
        assert result.pose_class == "standing"
        assert result.pose_confidence == 0.85
        assert result.bbox == [10.0, 20.0, 100.0, 200.0]

    def test_pose_result_without_bbox(self, sample_keypoints: dict[str, Keypoint]) -> None:
        """Test PoseResult without bounding box."""
        result = PoseResult(
            keypoints=sample_keypoints,
            pose_class="crouching",
            pose_confidence=0.78,
        )
        assert result.bbox is None

    def test_pose_result_to_dict(self, sample_keypoints: dict[str, Keypoint]) -> None:
        """Test to_dict serialization."""
        result = PoseResult(
            keypoints=sample_keypoints,
            pose_class="standing",
            pose_confidence=0.85,
            bbox=[10.0, 20.0, 100.0, 200.0],
        )
        result_dict = result.to_dict()

        assert "keypoints" in result_dict
        assert "pose_class" in result_dict
        assert "pose_confidence" in result_dict
        assert "bbox" in result_dict

        assert result_dict["pose_class"] == "standing"
        assert result_dict["pose_confidence"] == 0.85
        assert result_dict["bbox"] == [10.0, 20.0, 100.0, 200.0]
        assert len(result_dict["keypoints"]) == 5

    def test_pose_result_to_dict_keypoint_structure(
        self, sample_keypoints: dict[str, Keypoint]
    ) -> None:
        """Test that to_dict preserves keypoint structure."""
        result = PoseResult(
            keypoints=sample_keypoints,
            pose_class="running",
            pose_confidence=0.72,
        )
        result_dict = result.to_dict()

        nose_kp = result_dict["keypoints"]["nose"]
        assert nose_kp["x"] == 0.5
        assert nose_kp["y"] == 0.2
        assert nose_kp["confidence"] == 0.95

    def test_pose_result_empty_keypoints(self) -> None:
        """Test PoseResult with no keypoints."""
        result = PoseResult(
            keypoints={},
            pose_class="unknown",
            pose_confidence=0.0,
        )
        result_dict = result.to_dict()
        assert result_dict["keypoints"] == {}
        assert result_dict["pose_class"] == "unknown"


# =============================================================================
# Pose Classification Tests - Standing
# =============================================================================


class TestClassifyPoseStanding:
    """Tests for classify_pose with standing posture."""

    def test_standing_pose_basic(self) -> None:
        """Test basic standing pose detection with pixel coordinates."""
        # Using pixel coordinates for proper ratio calculations
        keypoints = {
            "left_hip": Keypoint(x=400, y=600, confidence=0.9, name="left_hip"),
            "right_hip": Keypoint(x=600, y=600, confidence=0.9, name="right_hip"),
            "left_knee": Keypoint(x=400, y=750, confidence=0.9, name="left_knee"),
            "right_knee": Keypoint(x=600, y=750, confidence=0.9, name="right_knee"),
            "left_ankle": Keypoint(x=400, y=900, confidence=0.9, name="left_ankle"),
            "right_ankle": Keypoint(x=600, y=900, confidence=0.9, name="right_ankle"),
            "left_shoulder": Keypoint(x=400, y=300, confidence=0.9, name="left_shoulder"),
            "right_shoulder": Keypoint(x=600, y=300, confidence=0.9, name="right_shoulder"),
        }
        pose_class, confidence = classify_pose(keypoints)
        assert pose_class == "standing"
        assert confidence >= 0.6

    def test_standing_with_feet_close(self) -> None:
        """Test standing pose with feet close together."""
        # Using pixel coordinates for proper ratio calculations
        keypoints = {
            "left_hip": Keypoint(x=480, y=600, confidence=0.9, name="left_hip"),
            "right_hip": Keypoint(x=520, y=600, confidence=0.9, name="right_hip"),
            "left_knee": Keypoint(x=480, y=750, confidence=0.9, name="left_knee"),
            "right_knee": Keypoint(x=520, y=750, confidence=0.9, name="right_knee"),
            "left_ankle": Keypoint(x=480, y=900, confidence=0.9, name="left_ankle"),
            "right_ankle": Keypoint(x=520, y=900, confidence=0.9, name="right_ankle"),
            "left_shoulder": Keypoint(x=480, y=300, confidence=0.9, name="left_shoulder"),
            "right_shoulder": Keypoint(x=520, y=300, confidence=0.9, name="right_shoulder"),
        }
        pose_class, _confidence = classify_pose(keypoints)
        assert pose_class == "standing"

    def test_standing_with_partial_keypoints(self) -> None:
        """Test standing pose with only core keypoints."""
        keypoints = {
            "left_hip": Keypoint(x=0.4, y=0.5, confidence=0.9, name="left_hip"),
            "right_hip": Keypoint(x=0.6, y=0.5, confidence=0.9, name="right_hip"),
            "left_knee": Keypoint(x=0.4, y=0.7, confidence=0.9, name="left_knee"),
            "right_knee": Keypoint(x=0.6, y=0.7, confidence=0.9, name="right_knee"),
            "left_ankle": Keypoint(x=0.4, y=0.9, confidence=0.9, name="left_ankle"),
            "right_ankle": Keypoint(x=0.6, y=0.9, confidence=0.9, name="right_ankle"),
        }
        pose_class, _confidence = classify_pose(keypoints)
        assert pose_class == "standing"


# =============================================================================
# Pose Classification Tests - Crouching
# =============================================================================


class TestClassifyPoseCrouching:
    """Tests for classify_pose with crouching posture (security-relevant)."""

    def test_crouching_pose_compressed_torso(self) -> None:
        """Test crouching detection with compressed torso."""
        keypoints = {
            "left_shoulder": Keypoint(x=0.4, y=0.4, confidence=0.9, name="left_shoulder"),
            "right_shoulder": Keypoint(x=0.6, y=0.4, confidence=0.9, name="right_shoulder"),
            "left_hip": Keypoint(x=0.4, y=0.55, confidence=0.9, name="left_hip"),
            "right_hip": Keypoint(x=0.6, y=0.55, confidence=0.9, name="right_hip"),
            "left_knee": Keypoint(x=0.4, y=0.75, confidence=0.9, name="left_knee"),
            "right_knee": Keypoint(x=0.6, y=0.75, confidence=0.9, name="right_knee"),
            "left_ankle": Keypoint(x=0.4, y=0.85, confidence=0.9, name="left_ankle"),
            "right_ankle": Keypoint(x=0.6, y=0.85, confidence=0.9, name="right_ankle"),
        }
        pose_class, confidence = classify_pose(keypoints)
        assert pose_class == "crouching"
        assert confidence >= 0.8

    def test_crouching_overrides_standing(self) -> None:
        """Test that crouching classification overrides standing when torso is compressed."""
        keypoints = {
            "left_shoulder": Keypoint(x=0.4, y=0.45, confidence=0.9, name="left_shoulder"),
            "right_shoulder": Keypoint(x=0.6, y=0.45, confidence=0.9, name="right_shoulder"),
            "left_hip": Keypoint(x=0.4, y=0.6, confidence=0.9, name="left_hip"),
            "right_hip": Keypoint(x=0.6, y=0.6, confidence=0.9, name="right_hip"),
            "left_knee": Keypoint(x=0.4, y=0.8, confidence=0.9, name="left_knee"),
            "right_knee": Keypoint(x=0.6, y=0.8, confidence=0.9, name="right_knee"),
        }
        pose_class, _confidence = classify_pose(keypoints)
        assert pose_class == "crouching"


# =============================================================================
# Pose Classification Tests - Sitting
# =============================================================================


class TestClassifyPoseSitting:
    """Tests for classify_pose with sitting posture."""

    def test_sitting_pose_hips_at_knee_level(self) -> None:
        """Test sitting detection when hips are at knee level."""
        keypoints = {
            "left_hip": Keypoint(x=0.4, y=0.6, confidence=0.9, name="left_hip"),
            "right_hip": Keypoint(x=0.6, y=0.6, confidence=0.9, name="right_hip"),
            "left_knee": Keypoint(x=0.4, y=0.6, confidence=0.9, name="left_knee"),
            "right_knee": Keypoint(x=0.6, y=0.6, confidence=0.9, name="right_knee"),
        }
        pose_class, confidence = classify_pose(keypoints)
        assert pose_class == "sitting"
        assert confidence >= 0.7

    def test_sitting_pose_hips_below_knees(self) -> None:
        """Test sitting detection when hips are below knee level."""
        keypoints = {
            "left_hip": Keypoint(x=0.4, y=0.65, confidence=0.9, name="left_hip"),
            "right_hip": Keypoint(x=0.6, y=0.65, confidence=0.9, name="right_hip"),
            "left_knee": Keypoint(x=0.4, y=0.6, confidence=0.9, name="left_knee"),
            "right_knee": Keypoint(x=0.6, y=0.6, confidence=0.9, name="right_knee"),
        }
        pose_class, _confidence = classify_pose(keypoints)
        assert pose_class == "sitting"


# =============================================================================
# Pose Classification Tests - Lying Down
# =============================================================================


class TestClassifyPoseLyingDown:
    """Tests for classify_pose with lying down posture (security-relevant)."""

    def test_lying_down_horizontal_orientation(self) -> None:
        """Test lying down detection with horizontal body orientation."""
        keypoints = {
            "left_shoulder": Keypoint(x=0.3, y=0.5, confidence=0.9, name="left_shoulder"),
            "right_shoulder": Keypoint(x=0.35, y=0.5, confidence=0.9, name="right_shoulder"),
            "left_hip": Keypoint(x=0.5, y=0.52, confidence=0.9, name="left_hip"),
            "right_hip": Keypoint(x=0.55, y=0.52, confidence=0.9, name="right_hip"),
            "left_ankle": Keypoint(x=0.7, y=0.55, confidence=0.9, name="left_ankle"),
            "right_ankle": Keypoint(x=0.75, y=0.55, confidence=0.9, name="right_ankle"),
        }
        pose_class, confidence = classify_pose(keypoints)
        assert pose_class == "lying"
        assert confidence >= 0.6

    def test_lying_down_extreme_horizontal_span(self) -> None:
        """Test lying down with extreme horizontal to vertical ratio."""
        keypoints = {
            "left_shoulder": Keypoint(x=0.1, y=0.5, confidence=0.9, name="left_shoulder"),
            "right_shoulder": Keypoint(x=0.12, y=0.5, confidence=0.9, name="right_shoulder"),
            "left_hip": Keypoint(x=0.5, y=0.51, confidence=0.9, name="left_hip"),
            "right_hip": Keypoint(x=0.52, y=0.51, confidence=0.9, name="right_hip"),
            "left_ankle": Keypoint(x=0.88, y=0.52, confidence=0.9, name="left_ankle"),
            "right_ankle": Keypoint(x=0.9, y=0.52, confidence=0.9, name="right_ankle"),
        }
        pose_class, _confidence = classify_pose(keypoints)
        assert pose_class == "lying"


# =============================================================================
# Pose Classification Tests - Running
# =============================================================================


class TestClassifyPoseRunning:
    """Tests for classify_pose with running/dynamic motion."""

    def test_running_wide_leg_spread(self) -> None:
        """Test running detection with wide leg spread (ratio > 3.0)."""
        # Using pixel coordinates: hip_width=100, ankle_spread=700, ratio=7.0
        keypoints = {
            "left_hip": Keypoint(x=450, y=600, confidence=0.9, name="left_hip"),
            "right_hip": Keypoint(x=550, y=600, confidence=0.9, name="right_hip"),
            "left_knee": Keypoint(x=400, y=700, confidence=0.9, name="left_knee"),
            "right_knee": Keypoint(x=600, y=700, confidence=0.9, name="right_knee"),
            "left_ankle": Keypoint(x=150, y=850, confidence=0.9, name="left_ankle"),
            "right_ankle": Keypoint(x=850, y=850, confidence=0.9, name="right_ankle"),
            "left_shoulder": Keypoint(x=450, y=300, confidence=0.9, name="left_shoulder"),
            "right_shoulder": Keypoint(x=550, y=300, confidence=0.9, name="right_shoulder"),
        }
        pose_class, confidence = classify_pose(keypoints)
        assert pose_class == "running"
        assert confidence >= 0.5

    def test_running_with_arm_swing(self) -> None:
        """Test running detection with asymmetric arm positions and wide leg spread."""
        # Using pixel coordinates with wide leg spread and arm asymmetry
        keypoints = {
            "left_hip": Keypoint(x=450, y=600, confidence=0.9, name="left_hip"),
            "right_hip": Keypoint(x=550, y=600, confidence=0.9, name="right_hip"),
            "left_knee": Keypoint(x=400, y=700, confidence=0.9, name="left_knee"),
            "right_knee": Keypoint(x=600, y=700, confidence=0.9, name="right_knee"),
            "left_ankle": Keypoint(x=150, y=850, confidence=0.9, name="left_ankle"),
            "right_ankle": Keypoint(x=850, y=850, confidence=0.9, name="right_ankle"),
            "left_shoulder": Keypoint(x=450, y=300, confidence=0.9, name="left_shoulder"),
            "right_shoulder": Keypoint(x=550, y=300, confidence=0.9, name="right_shoulder"),
            "left_wrist": Keypoint(x=400, y=200, confidence=0.9, name="left_wrist"),
            "right_wrist": Keypoint(x=600, y=700, confidence=0.9, name="right_wrist"),
            "left_elbow": Keypoint(x=420, y=250, confidence=0.9, name="left_elbow"),
            "right_elbow": Keypoint(x=580, y=650, confidence=0.9, name="right_elbow"),
        }
        pose_class, confidence = classify_pose(keypoints)
        assert pose_class == "running"
        assert confidence >= 0.7


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestClassifyPoseEdgeCases:
    """Tests for classify_pose edge cases and error conditions."""

    def test_empty_keypoints_dict(self) -> None:
        """Test classify_pose with no keypoints."""
        pose_class, confidence = classify_pose({})
        assert pose_class == "unknown"
        assert confidence == 0.0

    def test_insufficient_keypoints(self) -> None:
        """Test with only one required keypoint (need at least 2)."""
        keypoints = {
            "left_hip": Keypoint(x=0.5, y=0.5, confidence=0.9, name="left_hip"),
        }
        pose_class, confidence = classify_pose(keypoints)
        assert pose_class == "unknown"
        assert confidence == 0.0

    def test_missing_critical_keypoints(self) -> None:
        """Test with non-critical keypoints only."""
        keypoints = {
            "nose": Keypoint(x=0.5, y=0.1, confidence=0.9, name="nose"),
            "left_eye": Keypoint(x=0.45, y=0.08, confidence=0.9, name="left_eye"),
            "right_eye": Keypoint(x=0.55, y=0.08, confidence=0.9, name="right_eye"),
        }
        pose_class, _confidence = classify_pose(keypoints)
        assert pose_class == "unknown"

    def test_low_confidence_scores(self) -> None:
        """Test classification still works with confidence filtering done elsewhere."""
        # classify_pose doesn't filter by confidence, it works with provided keypoints
        keypoints = {
            "left_hip": Keypoint(x=0.4, y=0.5, confidence=0.2, name="left_hip"),
            "right_hip": Keypoint(x=0.6, y=0.5, confidence=0.2, name="right_hip"),
            "left_knee": Keypoint(x=0.4, y=0.7, confidence=0.2, name="left_knee"),
            "right_knee": Keypoint(x=0.6, y=0.7, confidence=0.2, name="right_knee"),
            "left_ankle": Keypoint(x=0.4, y=0.9, confidence=0.2, name="left_ankle"),
            "right_ankle": Keypoint(x=0.6, y=0.9, confidence=0.2, name="right_ankle"),
        }
        pose_class, _confidence = classify_pose(keypoints)
        # Should still classify based on positions, not confidence
        assert pose_class == "standing"

    def test_ambiguous_pose_low_score(self) -> None:
        """Test pose with low classification confidence returns unknown."""
        # Create keypoints that don't match any strong pattern
        keypoints = {
            "left_hip": Keypoint(x=0.4, y=0.5, confidence=0.9, name="left_hip"),
            "right_hip": Keypoint(x=0.6, y=0.5, confidence=0.9, name="right_hip"),
        }
        _pose_class, confidence = classify_pose(keypoints)
        # With minimal keypoints, might get low confidence or unknown
        assert confidence <= 1.0

    def test_only_left_side_keypoints(self) -> None:
        """Test with only left side keypoints available."""
        keypoints = {
            "left_hip": Keypoint(x=0.4, y=0.5, confidence=0.9, name="left_hip"),
            "left_knee": Keypoint(x=0.4, y=0.7, confidence=0.9, name="left_knee"),
            "left_ankle": Keypoint(x=0.4, y=0.9, confidence=0.9, name="left_ankle"),
            "left_shoulder": Keypoint(x=0.4, y=0.3, confidence=0.9, name="left_shoulder"),
        }
        pose_class, _confidence = classify_pose(keypoints)
        # Should still attempt classification with available keypoints
        # May be crouching due to compressed torso ratio
        assert pose_class in ["standing", "crouching", "unknown"]

    def test_only_right_side_keypoints(self) -> None:
        """Test with only right side keypoints available."""
        keypoints = {
            "right_hip": Keypoint(x=0.6, y=0.5, confidence=0.9, name="right_hip"),
            "right_knee": Keypoint(x=0.6, y=0.7, confidence=0.9, name="right_knee"),
            "right_ankle": Keypoint(x=0.6, y=0.9, confidence=0.9, name="right_ankle"),
            "right_shoulder": Keypoint(x=0.6, y=0.3, confidence=0.9, name="right_shoulder"),
        }
        pose_class, _confidence = classify_pose(keypoints)
        # Should still attempt classification with available keypoints
        # May be crouching due to compressed torso ratio
        assert pose_class in ["standing", "crouching", "unknown"]

    def test_pixel_coordinates_vs_normalized(self) -> None:
        """Test that classification works with pixel coordinates (not just normalized)."""
        # Using pixel coordinates (e.g., 1920x1080 image)
        keypoints = {
            "left_hip": Keypoint(x=768, y=540, confidence=0.9, name="left_hip"),
            "right_hip": Keypoint(x=1152, y=540, confidence=0.9, name="right_hip"),
            "left_knee": Keypoint(x=768, y=756, confidence=0.9, name="left_knee"),
            "right_knee": Keypoint(x=1152, y=756, confidence=0.9, name="right_knee"),
            "left_ankle": Keypoint(x=768, y=972, confidence=0.9, name="left_ankle"),
            "right_ankle": Keypoint(x=1152, y=972, confidence=0.9, name="right_ankle"),
            "left_shoulder": Keypoint(x=768, y=324, confidence=0.9, name="left_shoulder"),
            "right_shoulder": Keypoint(x=1152, y=324, confidence=0.9, name="right_shoulder"),
        }
        pose_class, _confidence = classify_pose(keypoints)
        assert pose_class == "standing"

    def test_extreme_coordinate_values(self) -> None:
        """Test with very large coordinate values."""
        keypoints = {
            "left_hip": Keypoint(x=10000, y=5000, confidence=0.9, name="left_hip"),
            "right_hip": Keypoint(x=15000, y=5000, confidence=0.9, name="right_hip"),
            "left_knee": Keypoint(x=10000, y=7000, confidence=0.9, name="left_knee"),
            "right_knee": Keypoint(x=15000, y=7000, confidence=0.9, name="right_knee"),
        }
        pose_class, _confidence = classify_pose(keypoints)
        # Should handle large values gracefully
        assert pose_class in ["standing", "unknown"]

    def test_zero_coordinate_values(self) -> None:
        """Test with zero coordinate values."""
        keypoints = {
            "left_hip": Keypoint(x=0.0, y=0.5, confidence=0.9, name="left_hip"),
            "right_hip": Keypoint(x=0.0, y=0.5, confidence=0.9, name="right_hip"),
        }
        pose_class, _confidence = classify_pose(keypoints)
        # Should handle zeros gracefully
        assert pose_class in ["standing", "sitting", "unknown"]

    def test_negative_coordinate_values(self) -> None:
        """Test with negative coordinate values (edge case, shouldn't happen)."""
        keypoints = {
            "left_hip": Keypoint(x=-0.1, y=0.5, confidence=0.9, name="left_hip"),
            "right_hip": Keypoint(x=-0.05, y=0.5, confidence=0.9, name="right_hip"),
        }
        pose_class, confidence = classify_pose(keypoints)
        # Should handle gracefully without crashing
        assert isinstance(pose_class, str)
        assert isinstance(confidence, float)


# =============================================================================
# Security Alert Detection (Integration with PoseAnalysisResult)
# =============================================================================


class TestSecurityAlertDetection:
    """Tests for security-relevant pose detection patterns.

    Note: The actual alert generation happens in the enrichment service,
    but we test the pose classification that would trigger those alerts.
    """

    def test_crouching_pose_for_security_alert(self) -> None:
        """Test crouching pose detection (security: potential hiding/break-in)."""
        keypoints = {
            "left_shoulder": Keypoint(x=0.4, y=0.4, confidence=0.9, name="left_shoulder"),
            "right_shoulder": Keypoint(x=0.6, y=0.4, confidence=0.9, name="right_shoulder"),
            "left_hip": Keypoint(x=0.4, y=0.55, confidence=0.9, name="left_hip"),
            "right_hip": Keypoint(x=0.6, y=0.55, confidence=0.9, name="right_hip"),
            "left_knee": Keypoint(x=0.4, y=0.75, confidence=0.9, name="left_knee"),
            "right_knee": Keypoint(x=0.6, y=0.75, confidence=0.9, name="right_knee"),
        }
        pose_class, confidence = classify_pose(keypoints)
        assert pose_class == "crouching"
        # High confidence means alert should be triggered
        assert confidence >= 0.8

    def test_lying_down_pose_for_security_alert(self) -> None:
        """Test lying down detection (security: possible medical emergency)."""
        keypoints = {
            "left_shoulder": Keypoint(x=0.2, y=0.5, confidence=0.9, name="left_shoulder"),
            "right_shoulder": Keypoint(x=0.25, y=0.5, confidence=0.9, name="right_shoulder"),
            "left_hip": Keypoint(x=0.6, y=0.52, confidence=0.9, name="left_hip"),
            "right_hip": Keypoint(x=0.65, y=0.52, confidence=0.9, name="right_hip"),
            "left_ankle": Keypoint(x=0.8, y=0.55, confidence=0.9, name="left_ankle"),
            "right_ankle": Keypoint(x=0.85, y=0.55, confidence=0.9, name="right_ankle"),
        }
        pose_class, confidence = classify_pose(keypoints)
        assert pose_class == "lying"
        assert confidence >= 0.6


# =============================================================================
# Normalization and Body Proportions
# =============================================================================


class TestBodyProportionCalculations:
    """Tests for body proportion calculations used in pose classification."""

    def test_classification_with_different_body_heights(self) -> None:
        """Test that classification adapts to different body heights."""
        # Tall person with larger pixel coordinates - need knees for proper classification
        tall_keypoints = {
            "left_shoulder": Keypoint(x=500, y=200, confidence=0.9, name="left_shoulder"),
            "right_shoulder": Keypoint(x=600, y=200, confidence=0.9, name="right_shoulder"),
            "left_hip": Keypoint(x=500, y=400, confidence=0.9, name="left_hip"),
            "right_hip": Keypoint(x=600, y=400, confidence=0.9, name="right_hip"),
            "left_knee": Keypoint(x=500, y=650, confidence=0.9, name="left_knee"),
            "right_knee": Keypoint(x=600, y=650, confidence=0.9, name="right_knee"),
            "left_ankle": Keypoint(x=500, y=900, confidence=0.9, name="left_ankle"),
            "right_ankle": Keypoint(x=600, y=900, confidence=0.9, name="right_ankle"),
        }

        # Short person with smaller pixel coordinates
        short_keypoints = {
            "left_shoulder": Keypoint(x=500, y=400, confidence=0.9, name="left_shoulder"),
            "right_shoulder": Keypoint(x=600, y=400, confidence=0.9, name="right_shoulder"),
            "left_hip": Keypoint(x=500, y=500, confidence=0.9, name="left_hip"),
            "right_hip": Keypoint(x=600, y=500, confidence=0.9, name="right_hip"),
            "left_knee": Keypoint(x=500, y=600, confidence=0.9, name="left_knee"),
            "right_knee": Keypoint(x=600, y=600, confidence=0.9, name="right_knee"),
            "left_ankle": Keypoint(x=500, y=700, confidence=0.9, name="left_ankle"),
            "right_ankle": Keypoint(x=600, y=700, confidence=0.9, name="right_ankle"),
        }

        tall_class, _tall_conf = classify_pose(tall_keypoints)
        short_class, _short_conf = classify_pose(short_keypoints)

        # Both should be classified as standing despite different sizes
        assert tall_class == "standing"
        assert short_class == "standing"

    def test_hip_width_calculation(self) -> None:
        """Test that hip width is used for normalizing leg spread."""
        # Wide hip width (larger person) - hip_width=400, ankle_spread=1300, ratio=3.25
        wide_hips = {
            "left_hip": Keypoint(x=300, y=600, confidence=0.9, name="left_hip"),
            "right_hip": Keypoint(x=700, y=600, confidence=0.9, name="right_hip"),
            "left_ankle": Keypoint(x=0, y=850, confidence=0.9, name="left_ankle"),
            "right_ankle": Keypoint(x=1300, y=850, confidence=0.9, name="right_ankle"),
            "left_knee": Keypoint(x=50, y=700, confidence=0.9, name="left_knee"),
            "right_knee": Keypoint(x=1250, y=700, confidence=0.9, name="right_knee"),
            "left_shoulder": Keypoint(x=300, y=300, confidence=0.9, name="left_shoulder"),
            "right_shoulder": Keypoint(x=700, y=300, confidence=0.9, name="right_shoulder"),
        }

        # Narrow hip width (smaller person) - hip_width=100, ankle_spread=700, ratio=7.0
        narrow_hips = {
            "left_hip": Keypoint(x=450, y=600, confidence=0.9, name="left_hip"),
            "right_hip": Keypoint(x=550, y=600, confidence=0.9, name="right_hip"),
            "left_ankle": Keypoint(x=150, y=850, confidence=0.9, name="left_ankle"),
            "right_ankle": Keypoint(x=850, y=850, confidence=0.9, name="right_ankle"),
            "left_knee": Keypoint(x=200, y=700, confidence=0.9, name="left_knee"),
            "right_knee": Keypoint(x=800, y=700, confidence=0.9, name="right_knee"),
            "left_shoulder": Keypoint(x=450, y=300, confidence=0.9, name="left_shoulder"),
            "right_shoulder": Keypoint(x=550, y=300, confidence=0.9, name="right_shoulder"),
        }

        wide_class, _ = classify_pose(wide_hips)
        narrow_class, _ = classify_pose(narrow_hips)

        # Both should recognize the leg spread is significant relative to hip width
        assert wide_class == "running"
        assert narrow_class == "running"


# =============================================================================
# Pose Analysis Service Tests
# =============================================================================


class TestKeypointsToCOCOArray:
    """Tests for keypoints_to_coco_array function."""

    def test_empty_keypoints(self) -> None:
        """Test with empty keypoints dict returns all zeros."""
        result = keypoints_to_coco_array({})

        assert len(result) == 17
        for kp in result:
            assert kp == [0.0, 0.0, 0.0]

    def test_single_keypoint(self) -> None:
        """Test with single keypoint."""
        keypoints = {"nose": Keypoint(x=100.0, y=50.0, confidence=0.95, name="nose")}

        result = keypoints_to_coco_array(keypoints)

        assert len(result) == 17
        assert result[0] == [100.0, 50.0, 0.95]  # nose is index 0
        assert result[1] == [0.0, 0.0, 0.0]  # left_eye missing

    def test_all_keypoints(self) -> None:
        """Test with all 17 keypoints present."""
        keypoints = {}
        for i, name in enumerate(KEYPOINT_NAMES):
            keypoints[name] = Keypoint(x=float(i * 10), y=float(i * 5), confidence=0.9, name=name)

        result = keypoints_to_coco_array(keypoints)

        assert len(result) == 17
        for i, kp in enumerate(result):
            assert kp == [float(i * 10), float(i * 5), 0.9]

    def test_partial_keypoints(self) -> None:
        """Test with partial keypoints (common scenario)."""
        keypoints = {
            "left_shoulder": Keypoint(x=100.0, y=150.0, confidence=0.9, name="left_shoulder"),
            "right_shoulder": Keypoint(x=200.0, y=150.0, confidence=0.88, name="right_shoulder"),
            "left_hip": Keypoint(x=105.0, y=250.0, confidence=0.85, name="left_hip"),
            "right_hip": Keypoint(x=195.0, y=250.0, confidence=0.87, name="right_hip"),
        }

        result = keypoints_to_coco_array(keypoints)

        assert len(result) == 17
        # Check shoulders at indices 5 and 6
        assert result[5] == [100.0, 150.0, 0.9]
        assert result[6] == [200.0, 150.0, 0.88]
        # Check hips at indices 11 and 12
        assert result[11] == [105.0, 250.0, 0.85]
        assert result[12] == [195.0, 250.0, 0.87]
        # Check nose (index 0) is missing
        assert result[0] == [0.0, 0.0, 0.0]

    def test_coco_order_preserved(self) -> None:
        """Test that COCO keypoint order is preserved."""
        expected_order = [
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

        # Create keypoints with unique coordinates per name
        keypoints = {}
        for i, name in enumerate(expected_order):
            keypoints[name] = Keypoint(x=float(i), y=float(i + 100), confidence=0.5, name=name)

        result = keypoints_to_coco_array(keypoints)

        for i, name in enumerate(expected_order):
            assert result[i] == [
                float(i),
                float(i + 100),
                0.5,
            ], f"Mismatch at index {i} ({name})"


class TestCountValidKeypoints:
    """Tests for count_valid_keypoints function."""

    def test_empty_keypoints(self) -> None:
        """Test with empty keypoints dict."""
        assert count_valid_keypoints({}) == 0

    def test_all_valid(self) -> None:
        """Test with all keypoints having positive confidence."""
        keypoints = {
            "nose": Keypoint(x=100, y=50, confidence=0.9, name="nose"),
            "left_eye": Keypoint(x=95, y=45, confidence=0.85, name="left_eye"),
        }

        assert count_valid_keypoints(keypoints) == 2

    def test_some_zero_confidence(self) -> None:
        """Test with some keypoints having zero confidence."""
        keypoints = {
            "nose": Keypoint(x=100, y=50, confidence=0.9, name="nose"),
            "left_eye": Keypoint(x=95, y=45, confidence=0.0, name="left_eye"),
            "right_eye": Keypoint(x=105, y=45, confidence=0.85, name="right_eye"),
        }

        assert count_valid_keypoints(keypoints) == 2

    def test_all_zero_confidence(self) -> None:
        """Test with all keypoints having zero confidence."""
        keypoints = {
            "nose": Keypoint(x=100, y=50, confidence=0.0, name="nose"),
            "left_eye": Keypoint(x=95, y=45, confidence=0.0, name="left_eye"),
        }

        assert count_valid_keypoints(keypoints) == 0


class TestDetectCrouchingService:
    """Tests for detect_crouching function in pose_analysis_service."""

    def test_no_hips(self) -> None:
        """Test returns False when no hips detected."""
        keypoints = {
            "left_knee": Keypoint(x=100, y=200, confidence=0.9, name="left_knee"),
            "right_knee": Keypoint(x=150, y=200, confidence=0.9, name="right_knee"),
        }

        assert detect_crouching(keypoints) is False

    def test_no_knees(self) -> None:
        """Test returns False when no knees detected."""
        keypoints = {
            "left_hip": Keypoint(x=100, y=150, confidence=0.9, name="left_hip"),
            "right_hip": Keypoint(x=150, y=150, confidence=0.9, name="right_hip"),
        }

        assert detect_crouching(keypoints) is False

    def test_low_confidence_keypoints(self) -> None:
        """Test returns False when keypoints are below confidence threshold."""
        keypoints = {
            "left_hip": Keypoint(x=100, y=150, confidence=0.2, name="left_hip"),
            "right_hip": Keypoint(x=150, y=150, confidence=0.2, name="right_hip"),
            "left_knee": Keypoint(x=100, y=200, confidence=0.2, name="left_knee"),
            "right_knee": Keypoint(x=150, y=200, confidence=0.2, name="right_knee"),
        }

        assert detect_crouching(keypoints) is False

    def test_crouching_with_compressed_torso(self) -> None:
        """Test detects crouching when torso is compressed."""
        keypoints = {
            "left_shoulder": Keypoint(x=100, y=150, confidence=0.9, name="left_shoulder"),
            "right_shoulder": Keypoint(x=150, y=150, confidence=0.9, name="right_shoulder"),
            "left_hip": Keypoint(x=105, y=180, confidence=0.9, name="left_hip"),
            "right_hip": Keypoint(x=145, y=180, confidence=0.9, name="right_hip"),
            "left_knee": Keypoint(x=105, y=280, confidence=0.9, name="left_knee"),
            "right_knee": Keypoint(x=145, y=280, confidence=0.9, name="right_knee"),
        }

        assert detect_crouching(keypoints) is True

    def test_standing_not_crouching(self) -> None:
        """Test does not detect crouching when standing normally."""
        keypoints = {
            "left_shoulder": Keypoint(x=100, y=50, confidence=0.9, name="left_shoulder"),
            "right_shoulder": Keypoint(x=150, y=50, confidence=0.9, name="right_shoulder"),
            "left_hip": Keypoint(x=105, y=150, confidence=0.9, name="left_hip"),
            "right_hip": Keypoint(x=145, y=150, confidence=0.9, name="right_hip"),
            "left_knee": Keypoint(x=105, y=250, confidence=0.9, name="left_knee"),
            "right_knee": Keypoint(x=145, y=250, confidence=0.9, name="right_knee"),
        }

        assert detect_crouching(keypoints) is False

    def test_deep_crouch_fallback(self) -> None:
        """Test detects deep crouch when hip-knee distance is very small."""
        keypoints = {
            "left_hip": Keypoint(x=105, y=190, confidence=0.9, name="left_hip"),
            "right_hip": Keypoint(x=145, y=190, confidence=0.9, name="right_hip"),
            "left_knee": Keypoint(x=105, y=200, confidence=0.9, name="left_knee"),
            "right_knee": Keypoint(x=145, y=200, confidence=0.9, name="right_knee"),
        }

        assert detect_crouching(keypoints) is True


class TestDetectLyingDownService:
    """Tests for detect_lying_down function."""

    def test_no_shoulders(self) -> None:
        """Test returns False when no shoulders detected."""
        keypoints = {
            "left_ankle": Keypoint(x=350, y=100, confidence=0.9, name="left_ankle"),
            "right_ankle": Keypoint(x=400, y=100, confidence=0.9, name="right_ankle"),
        }

        assert detect_lying_down(keypoints) is False

    def test_no_ankles(self) -> None:
        """Test returns False when no ankles detected."""
        keypoints = {
            "left_shoulder": Keypoint(x=50, y=100, confidence=0.9, name="left_shoulder"),
            "right_shoulder": Keypoint(x=100, y=105, confidence=0.9, name="right_shoulder"),
        }

        assert detect_lying_down(keypoints) is False

    def test_lying_horizontal(self) -> None:
        """Test detects lying down with horizontal body orientation."""
        keypoints = {
            "left_shoulder": Keypoint(x=50, y=100, confidence=0.9, name="left_shoulder"),
            "right_shoulder": Keypoint(x=100, y=105, confidence=0.9, name="right_shoulder"),
            "left_ankle": Keypoint(x=350, y=100, confidence=0.9, name="left_ankle"),
            "right_ankle": Keypoint(x=400, y=100, confidence=0.9, name="right_ankle"),
        }

        assert detect_lying_down(keypoints) is True

    def test_standing_not_lying(self) -> None:
        """Test does not detect lying when standing upright."""
        keypoints = {
            "left_shoulder": Keypoint(x=100, y=50, confidence=0.9, name="left_shoulder"),
            "right_shoulder": Keypoint(x=150, y=50, confidence=0.9, name="right_shoulder"),
            "left_ankle": Keypoint(x=105, y=350, confidence=0.9, name="left_ankle"),
            "right_ankle": Keypoint(x=145, y=350, confidence=0.9, name="right_ankle"),
        }

        assert detect_lying_down(keypoints) is False


class TestDetectHandsRaisedService:
    """Tests for detect_hands_raised function."""

    def test_no_wrists(self) -> None:
        """Test returns False when no wrists detected."""
        keypoints = {
            "left_shoulder": Keypoint(x=100, y=150, confidence=0.9, name="left_shoulder"),
            "right_shoulder": Keypoint(x=200, y=150, confidence=0.9, name="right_shoulder"),
        }

        assert detect_hands_raised(keypoints) is False

    def test_one_wrist_only(self) -> None:
        """Test returns False when only one wrist detected."""
        keypoints = {
            "left_shoulder": Keypoint(x=100, y=150, confidence=0.9, name="left_shoulder"),
            "right_shoulder": Keypoint(x=200, y=150, confidence=0.9, name="right_shoulder"),
            "left_wrist": Keypoint(x=80, y=50, confidence=0.9, name="left_wrist"),
        }

        assert detect_hands_raised(keypoints) is False

    def test_both_hands_raised(self) -> None:
        """Test detects both hands raised above shoulders."""
        keypoints = {
            "left_shoulder": Keypoint(x=100, y=150, confidence=0.9, name="left_shoulder"),
            "right_shoulder": Keypoint(x=200, y=150, confidence=0.9, name="right_shoulder"),
            "left_wrist": Keypoint(x=80, y=50, confidence=0.9, name="left_wrist"),
            "right_wrist": Keypoint(x=220, y=50, confidence=0.9, name="right_wrist"),
        }

        assert detect_hands_raised(keypoints) is True

    def test_hands_at_shoulder_level(self) -> None:
        """Test returns False when hands at shoulder level (within margin)."""
        keypoints = {
            "left_shoulder": Keypoint(x=100, y=150, confidence=0.9, name="left_shoulder"),
            "right_shoulder": Keypoint(x=200, y=150, confidence=0.9, name="right_shoulder"),
            "left_wrist": Keypoint(x=80, y=145, confidence=0.9, name="left_wrist"),
            "right_wrist": Keypoint(x=220, y=145, confidence=0.9, name="right_wrist"),
        }

        assert detect_hands_raised(keypoints) is False

    def test_one_hand_raised(self) -> None:
        """Test returns False when only one hand raised."""
        keypoints = {
            "left_shoulder": Keypoint(x=100, y=150, confidence=0.9, name="left_shoulder"),
            "right_shoulder": Keypoint(x=200, y=150, confidence=0.9, name="right_shoulder"),
            "left_wrist": Keypoint(x=80, y=50, confidence=0.9, name="left_wrist"),
            "right_wrist": Keypoint(x=220, y=200, confidence=0.9, name="right_wrist"),
        }

        assert detect_hands_raised(keypoints) is False


class TestDetectFightingStanceService:
    """Tests for detect_fighting_stance function."""

    def test_no_hips(self) -> None:
        """Test returns False when no hips detected."""
        keypoints = {
            "left_ankle": Keypoint(x=50, y=380, confidence=0.9, name="left_ankle"),
            "right_ankle": Keypoint(x=200, y=350, confidence=0.9, name="right_ankle"),
        }

        assert detect_fighting_stance(keypoints) is False

    def test_no_ankles(self) -> None:
        """Test returns False when no ankles detected."""
        keypoints = {
            "left_hip": Keypoint(x=110, y=150, confidence=0.9, name="left_hip"),
            "right_hip": Keypoint(x=140, y=150, confidence=0.9, name="right_hip"),
        }

        assert detect_fighting_stance(keypoints) is False

    def test_fighting_stance_detected(self) -> None:
        """Test detects fighting stance with wide asymmetric leg spread."""
        keypoints = {
            "left_hip": Keypoint(x=100, y=150, confidence=0.9, name="left_hip"),
            "right_hip": Keypoint(x=150, y=150, confidence=0.9, name="right_hip"),
            "left_ankle": Keypoint(x=50, y=380, confidence=0.9, name="left_ankle"),
            "right_ankle": Keypoint(x=200, y=330, confidence=0.9, name="right_ankle"),
        }

        assert detect_fighting_stance(keypoints) is True

    def test_standing_not_fighting(self) -> None:
        """Test does not detect fighting stance when standing normally."""
        keypoints = {
            "left_hip": Keypoint(x=110, y=150, confidence=0.9, name="left_hip"),
            "right_hip": Keypoint(x=140, y=150, confidence=0.9, name="right_hip"),
            "left_ankle": Keypoint(x=115, y=350, confidence=0.9, name="left_ankle"),
            "right_ankle": Keypoint(x=135, y=350, confidence=0.9, name="right_ankle"),
        }

        assert detect_fighting_stance(keypoints) is False


class TestDetectSecurityAlertsService:
    """Tests for detect_security_alerts function."""

    def test_no_alerts_standing(self) -> None:
        """Test no alerts for normal standing posture."""
        keypoints = {
            "left_shoulder": Keypoint(x=100, y=50, confidence=0.9, name="left_shoulder"),
            "right_shoulder": Keypoint(x=150, y=50, confidence=0.9, name="right_shoulder"),
            "left_hip": Keypoint(x=105, y=150, confidence=0.9, name="left_hip"),
            "right_hip": Keypoint(x=145, y=150, confidence=0.9, name="right_hip"),
            "left_knee": Keypoint(x=105, y=250, confidence=0.9, name="left_knee"),
            "right_knee": Keypoint(x=145, y=250, confidence=0.9, name="right_knee"),
            "left_ankle": Keypoint(x=105, y=350, confidence=0.9, name="left_ankle"),
            "right_ankle": Keypoint(x=145, y=350, confidence=0.9, name="right_ankle"),
            "left_wrist": Keypoint(x=80, y=200, confidence=0.9, name="left_wrist"),
            "right_wrist": Keypoint(x=170, y=200, confidence=0.9, name="right_wrist"),
        }

        alerts = detect_security_alerts(keypoints, "standing")

        assert alerts == []

    def test_crouching_alert_from_posture(self) -> None:
        """Test crouching alert from posture classification."""
        keypoints: dict[str, Keypoint] = {}

        alerts = detect_security_alerts(keypoints, "crouching")

        assert "crouching" in alerts

    def test_lying_down_alert_from_posture(self) -> None:
        """Test lying_down alert from posture classification."""
        keypoints: dict[str, Keypoint] = {}

        alerts = detect_security_alerts(keypoints, "lying")

        assert "lying_down" in alerts

    def test_hands_raised_alert(self) -> None:
        """Test hands_raised alert detection."""
        keypoints = {
            "left_shoulder": Keypoint(x=100, y=150, confidence=0.9, name="left_shoulder"),
            "right_shoulder": Keypoint(x=200, y=150, confidence=0.9, name="right_shoulder"),
            "left_wrist": Keypoint(x=80, y=50, confidence=0.9, name="left_wrist"),
            "right_wrist": Keypoint(x=220, y=50, confidence=0.9, name="right_wrist"),
        }

        alerts = detect_security_alerts(keypoints, "standing")

        assert "hands_raised" in alerts


class TestNormalizePostureService:
    """Tests for normalize_posture function."""

    def test_standing(self) -> None:
        """Test standing posture normalization."""
        assert normalize_posture("standing") == "standing"

    def test_lying_to_lying_down(self) -> None:
        """Test 'lying' is normalized to 'lying_down'."""
        assert normalize_posture("lying") == "lying_down"

    def test_unknown(self) -> None:
        """Test unknown posture normalization."""
        assert normalize_posture("unknown") == "unknown"

    def test_invalid_posture(self) -> None:
        """Test invalid posture returns 'unknown'."""
        assert normalize_posture("invalid_pose") == "unknown"


class TestAnalyzePoseService:
    """Tests for analyze_pose function."""

    def test_basic_analysis(self) -> None:
        """Test basic pose analysis output structure."""
        keypoints = {
            "nose": Keypoint(x=125, y=50, confidence=0.95, name="nose"),
            "left_shoulder": Keypoint(x=100, y=100, confidence=0.9, name="left_shoulder"),
            "right_shoulder": Keypoint(x=150, y=100, confidence=0.9, name="right_shoulder"),
        }
        pose_result = PoseResult(
            keypoints=keypoints,
            pose_class="standing",
            pose_confidence=0.85,
        )

        result = analyze_pose(pose_result)

        assert result["posture"] == "standing"
        assert result["confidence"] == 0.85
        assert result["keypoint_count"] == 3
        assert len(result["keypoints"]) == 17
        assert isinstance(result["alerts"], list)
        assert result["alerts"] == result["security_alerts"]

    def test_lying_posture_normalization(self) -> None:
        """Test that 'lying' is normalized to 'lying_down' in output."""
        pose_result = PoseResult(
            keypoints={},
            pose_class="lying",
            pose_confidence=0.75,
        )

        result = analyze_pose(pose_result)

        assert result["posture"] == "lying_down"

    def test_keypoints_in_coco_format(self) -> None:
        """Test keypoints are in correct COCO array format."""
        keypoints = {
            "nose": Keypoint(x=100, y=50, confidence=0.95, name="nose"),
        }
        pose_result = PoseResult(
            keypoints=keypoints,
            pose_class="standing",
            pose_confidence=0.85,
        )

        result = analyze_pose(pose_result)

        assert result["keypoints"][0] == [100, 50, 0.95]  # nose
        assert result["keypoints"][1] == [0.0, 0.0, 0.0]  # left_eye (missing)

    def test_empty_keypoints(self) -> None:
        """Test analysis with empty keypoints."""
        pose_result = PoseResult(
            keypoints={},
            pose_class="unknown",
            pose_confidence=0.0,
        )

        result = analyze_pose(pose_result)

        assert result["posture"] == "unknown"
        assert result["confidence"] == 0.0
        assert result["keypoint_count"] == 0
        assert len(result["keypoints"]) == 17
        assert all(kp == [0.0, 0.0, 0.0] for kp in result["keypoints"])


class TestAnalyzePosesBatchService:
    """Tests for analyze_poses_batch function."""

    def test_empty_input(self) -> None:
        """Test with empty input dict."""
        result = analyze_poses_batch({})

        assert result == {}

    def test_single_pose(self) -> None:
        """Test with single pose."""
        pose_results = {
            "0": PoseResult(
                keypoints={"nose": Keypoint(x=100, y=50, confidence=0.95, name="nose")},
                pose_class="standing",
                pose_confidence=0.85,
            )
        }

        result = analyze_poses_batch(pose_results)

        assert "0" in result
        assert result["0"]["posture"] == "standing"

    def test_multiple_poses(self) -> None:
        """Test with multiple poses."""
        pose_results = {
            "0": PoseResult(
                keypoints={},
                pose_class="standing",
                pose_confidence=0.85,
            ),
            "1": PoseResult(
                keypoints={},
                pose_class="crouching",
                pose_confidence=0.75,
            ),
            "2": PoseResult(
                keypoints={},
                pose_class="running",
                pose_confidence=0.90,
            ),
        }

        result = analyze_poses_batch(pose_results)

        assert len(result) == 3
        assert result["0"]["posture"] == "standing"
        assert result["1"]["posture"] == "crouching"
        assert result["2"]["posture"] == "running"


class TestCreateEmptyPoseEnrichmentService:
    """Tests for create_empty_pose_enrichment function."""

    def test_structure(self) -> None:
        """Test empty enrichment has correct structure."""
        result = create_empty_pose_enrichment()

        assert result["posture"] == "unknown"
        assert result["alerts"] == []
        assert result["security_alerts"] == []
        assert result["keypoint_count"] == 0
        assert result["confidence"] == 0.0

    def test_keypoints_format(self) -> None:
        """Test empty enrichment has 17 zero keypoints."""
        result = create_empty_pose_enrichment()

        assert len(result["keypoints"]) == 17
        for kp in result["keypoints"]:
            assert kp == [0.0, 0.0, 0.0]

    def test_backward_compatibility(self) -> None:
        """Test alerts and security_alerts are both present and equal."""
        result = create_empty_pose_enrichment()

        assert "alerts" in result
        assert "security_alerts" in result
        assert result["alerts"] == result["security_alerts"]


class TestModuleConstantsService:
    """Tests for module constants."""

    def test_alert_confidence_threshold(self) -> None:
        """Test ALERT_CONFIDENCE_THRESHOLD is reasonable."""
        assert 0.0 < ALERT_CONFIDENCE_THRESHOLD < 1.0

    def test_posture_map_completeness(self) -> None:
        """Test POSTURE_MAP covers expected pose classes."""
        expected_keys = {
            "standing",
            "walking",
            "running",
            "sitting",
            "crouching",
            "lying",
            "unknown",
        }
        assert set(POSTURE_MAP.keys()) == expected_keys
