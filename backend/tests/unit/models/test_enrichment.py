"""Unit tests for enrichment models (PoseResult, ThreatDetection, etc.).

Tests cover:
- Model instantiation with valid data
- Field validation and constraints
- Default values
- Relationship navigation
- String representation (__repr__)
- CheckConstraints for enum values
- Property-based tests for numeric fields
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.models.enrichment import ActionResult, PoseResult, ThreatDetection

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# Custom Strategies for Property-Based Testing
# =============================================================================

# Strategy for valid confidence scores (0.0 to 1.0)
confidence_scores = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)

# Strategy for valid pose classes
pose_classes = st.sampled_from(
    ["standing", "crouching", "bending_over", "arms_raised", "sitting", "lying_down", "unknown"]
)

# Strategy for valid threat types
threat_types = st.sampled_from(["gun", "knife", "grenade", "explosive", "weapon", "other"])

# Strategy for valid severity levels
severity_levels = st.sampled_from(["critical", "high", "medium", "low"])

# =============================================================================
# PoseResult Model Tests
# =============================================================================


class TestPoseResultModel:
    """Tests for PoseResult model."""

    def test_pose_result_creation_minimal(self):
        """Test creating a pose result with minimal required fields."""
        pose = PoseResult(detection_id=1)
        assert pose.detection_id == 1
        assert pose.keypoints is None
        assert pose.pose_class is None
        assert pose.confidence is None
        # Default applies at DB level, not in-memory without database insert
        assert pose.is_suspicious in (None, False)

    def test_pose_result_creation_full(self):
        """Test creating a pose result with all fields."""
        keypoints = [[100.0, 200.0, 0.95] for _ in range(17)]  # 17 COCO keypoints
        pose = PoseResult(
            detection_id=1,
            keypoints=keypoints,
            pose_class="crouching",
            confidence=0.92,
            is_suspicious=True,
        )
        assert pose.detection_id == 1
        assert len(pose.keypoints) == 17
        assert pose.pose_class == "crouching"
        assert pose.confidence == 0.92
        assert pose.is_suspicious is True

    def test_pose_result_default_is_suspicious(self):
        """Test is_suspicious has default defined at column level."""
        from sqlalchemy import inspect

        mapper = inspect(PoseResult)
        is_suspicious_col = mapper.columns["is_suspicious"]
        assert is_suspicious_col.default is not None
        assert is_suspicious_col.default.arg is False

    def test_pose_result_repr(self):
        """Test PoseResult __repr__ method."""
        pose = PoseResult(id=1, detection_id=42, pose_class="standing", is_suspicious=False)
        repr_str = repr(pose)
        assert "PoseResult" in repr_str
        assert "id=1" in repr_str
        assert "detection_id=42" in repr_str
        assert "pose_class='standing'" in repr_str
        assert "is_suspicious=False" in repr_str

    def test_pose_result_has_detection_relationship(self):
        """Test PoseResult has detection relationship defined."""
        pose = PoseResult(detection_id=1)
        assert hasattr(pose, "detection")

    def test_pose_result_tablename(self):
        """Test PoseResult has correct table name."""
        assert PoseResult.__tablename__ == "pose_results"

    def test_pose_result_has_indexes(self):
        """Test PoseResult has expected indexes."""
        indexes = PoseResult.__table_args__
        index_names = [idx.name for idx in indexes if hasattr(idx, "name")]
        assert "idx_pose_results_detection_id" in index_names
        assert "idx_pose_results_created_at" in index_names
        assert "idx_pose_results_is_suspicious" in index_names

    @given(confidence=confidence_scores)
    @settings(max_examples=30)
    def test_pose_result_confidence_roundtrip(self, confidence: float):
        """Property: Confidence values roundtrip correctly."""
        pose = PoseResult(detection_id=1, confidence=confidence)
        assert abs(pose.confidence - confidence) < 1e-10

    @given(pose_class=pose_classes)
    @settings(max_examples=10)
    def test_pose_result_pose_class_roundtrip(self, pose_class: str):
        """Property: Pose class values roundtrip correctly."""
        pose = PoseResult(detection_id=1, pose_class=pose_class)
        assert pose.pose_class == pose_class


# =============================================================================
# ThreatDetection Model Tests
# =============================================================================


class TestThreatDetectionModel:
    """Tests for ThreatDetection model."""

    def test_threat_detection_creation_minimal(self):
        """Test creating a threat detection with required fields."""
        threat = ThreatDetection(
            detection_id=1, threat_type="gun", confidence=0.95, severity="critical"
        )
        assert threat.detection_id == 1
        assert threat.threat_type == "gun"
        assert threat.confidence == 0.95
        assert threat.severity == "critical"
        assert threat.bbox is None

    def test_threat_detection_creation_full(self):
        """Test creating a threat detection with all fields."""
        threat = ThreatDetection(
            detection_id=1,
            threat_type="knife",
            confidence=0.88,
            severity="high",
            bbox=[100, 200, 150, 250],
        )
        assert threat.detection_id == 1
        assert threat.threat_type == "knife"
        assert threat.confidence == 0.88
        assert threat.severity == "high"
        assert threat.bbox == [100, 200, 150, 250]

    def test_threat_detection_multiple_for_same_detection(self):
        """Test multiple threat detections can exist for one detection."""
        threat1 = ThreatDetection(
            detection_id=1, threat_type="gun", confidence=0.95, severity="critical"
        )
        threat2 = ThreatDetection(
            detection_id=1, threat_type="knife", confidence=0.80, severity="high"
        )
        assert threat1.detection_id == threat2.detection_id
        assert threat1.threat_type != threat2.threat_type

    def test_threat_detection_repr(self):
        """Test ThreatDetection __repr__ method."""
        threat = ThreatDetection(id=1, detection_id=42, threat_type="gun", severity="critical")
        repr_str = repr(threat)
        assert "ThreatDetection" in repr_str
        assert "id=1" in repr_str
        assert "detection_id=42" in repr_str
        assert "threat_type='gun'" in repr_str
        assert "severity='critical'" in repr_str

    def test_threat_detection_has_detection_relationship(self):
        """Test ThreatDetection has detection relationship defined."""
        threat = ThreatDetection(
            detection_id=1, threat_type="gun", confidence=0.95, severity="critical"
        )
        assert hasattr(threat, "detection")

    def test_threat_detection_tablename(self):
        """Test ThreatDetection has correct table name."""
        assert ThreatDetection.__tablename__ == "threat_detections"

    def test_threat_detection_has_indexes(self):
        """Test ThreatDetection has expected indexes."""
        indexes = ThreatDetection.__table_args__
        index_names = [idx.name for idx in indexes if hasattr(idx, "name")]
        assert "idx_threat_detections_detection_id" in index_names
        assert "idx_threat_detections_created_at" in index_names
        assert "idx_threat_detections_threat_type" in index_names
        assert "idx_threat_detections_severity" in index_names
        assert "idx_threat_detections_type_severity" in index_names

    @given(confidence=confidence_scores)
    @settings(max_examples=30)
    def test_threat_detection_confidence_roundtrip(self, confidence: float):
        """Property: Confidence values roundtrip correctly."""
        threat = ThreatDetection(
            detection_id=1, threat_type="gun", confidence=confidence, severity="high"
        )
        assert abs(threat.confidence - confidence) < 1e-10

    @given(threat_type=threat_types, severity=severity_levels)
    @settings(max_examples=20)
    def test_threat_detection_type_severity_roundtrip(self, threat_type: str, severity: str):
        """Property: Threat type and severity values roundtrip correctly."""
        threat = ThreatDetection(
            detection_id=1, threat_type=threat_type, confidence=0.8, severity=severity
        )
        assert threat.threat_type == threat_type
        assert threat.severity == severity


# =============================================================================
# ActionResult Model Tests
#
# (DemographicsResult / ReIDEmbedding model tests retired with their tables in
# R8 S4 -- see backend/tests/unit/models/
# test_r8_s4_demographics_reid_retirement.py for the guard.)
# =============================================================================


class TestActionResultModel:
    """Tests for ActionResult model."""

    def test_action_result_creation_minimal(self):
        """Test creating an action result with minimal fields."""
        action = ActionResult(detection_id=1)
        assert action.detection_id == 1
        assert action.action is None
        assert action.confidence is None
        # Default applies at DB level, not in-memory without database insert
        assert action.is_suspicious in (None, False)
        assert action.all_scores is None

    def test_action_result_creation_full(self):
        """Test creating an action result with all fields."""
        all_scores = {
            "walking": 0.85,
            "running": 0.10,
            "standing": 0.05,
        }
        action = ActionResult(
            detection_id=1,
            action="walking",
            confidence=0.85,
            is_suspicious=False,
            all_scores=all_scores,
        )
        assert action.detection_id == 1
        assert action.action == "walking"
        assert action.confidence == 0.85
        assert action.is_suspicious is False
        assert action.all_scores == all_scores

    def test_action_result_suspicious_action(self):
        """Test action result with suspicious flag."""
        action = ActionResult(
            detection_id=1,
            action="climbing",
            confidence=0.88,
            is_suspicious=True,
        )
        assert action.action == "climbing"
        assert action.is_suspicious is True

    def test_action_result_default_is_suspicious(self):
        """Test is_suspicious has default defined at column level."""
        from sqlalchemy import inspect

        mapper = inspect(ActionResult)
        is_suspicious_col = mapper.columns["is_suspicious"]
        assert is_suspicious_col.default is not None
        assert is_suspicious_col.default.arg is False

    def test_action_result_repr(self):
        """Test ActionResult __repr__ method."""
        action = ActionResult(id=1, detection_id=42, action="walking", is_suspicious=False)
        repr_str = repr(action)
        assert "ActionResult" in repr_str
        assert "id=1" in repr_str
        assert "detection_id=42" in repr_str
        assert "action='walking'" in repr_str
        assert "is_suspicious=False" in repr_str

    def test_action_result_has_detection_relationship(self):
        """Test ActionResult has detection relationship defined."""
        action = ActionResult(detection_id=1)
        assert hasattr(action, "detection")

    def test_action_result_tablename(self):
        """Test ActionResult has correct table name."""
        assert ActionResult.__tablename__ == "action_results"

    def test_action_result_has_indexes(self):
        """Test ActionResult has expected indexes."""
        indexes = ActionResult.__table_args__
        index_names = [idx.name for idx in indexes if hasattr(idx, "name")]
        assert "idx_action_results_detection_id" in index_names
        assert "idx_action_results_created_at" in index_names
        assert "idx_action_results_action" in index_names
        assert "idx_action_results_is_suspicious" in index_names

    @given(confidence=confidence_scores)
    @settings(max_examples=30)
    def test_action_result_confidence_roundtrip(self, confidence: float):
        """Property: Confidence values roundtrip correctly."""
        action = ActionResult(detection_id=1, confidence=confidence)
        assert abs(action.confidence - confidence) < 1e-10
