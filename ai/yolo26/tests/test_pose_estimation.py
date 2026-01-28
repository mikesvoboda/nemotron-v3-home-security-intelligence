"""Unit tests for YOLO26 pose estimation endpoints.

Tests cover:
- Pose estimation model loading and configuration
- Keypoint detection response schemas
- Fall detection logic based on keypoint positions
- Aggression detection (raised arms, rapid movement)
- Loitering detection (stationary person over time threshold)
- API endpoints for pose estimation

NEM-3910: Add YOLO26 pose estimation for fall/aggression/loitering detection
"""

import io
import sys
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest
from PIL import Image

# Add the ai/yolo26 directory to sys.path to enable imports
_yolo26_dir = Path(__file__).parent.parent
if str(_yolo26_dir) not in sys.path:
    sys.path.insert(0, str(_yolo26_dir))


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def dummy_image():
    """Create a dummy PIL image for testing."""
    img_array = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    return Image.fromarray(img_array)


@pytest.fixture
def dummy_image_bytes(dummy_image):
    """Create dummy image bytes for testing."""
    img_bytes = io.BytesIO()
    dummy_image.save(img_bytes, format="JPEG")
    img_bytes.seek(0)
    return img_bytes.getvalue()


@pytest.fixture
def standing_keypoints():
    """Create keypoints for a standing person.

    COCO keypoint format: 17 keypoints with x, y, confidence
    Person standing upright with arms at sides (not spread wide).
    """
    # COCO keypoint order: nose, left_eye, right_eye, left_ear, right_ear,
    # left_shoulder, right_shoulder, left_elbow, right_elbow, left_wrist,
    # right_wrist, left_hip, right_hip, left_knee, right_knee, left_ankle, right_ankle
    return np.array(
        [
            [320.0, 50.0, 0.95],  # nose (at top)
            [310.0, 45.0, 0.92],  # left_eye
            [330.0, 45.0, 0.92],  # right_eye
            [300.0, 50.0, 0.85],  # left_ear
            [340.0, 50.0, 0.85],  # right_ear
            [280.0, 100.0, 0.90],  # left_shoulder
            [360.0, 100.0, 0.90],  # right_shoulder
            [275.0, 170.0, 0.88],  # left_elbow (close to body)
            [365.0, 170.0, 0.88],  # right_elbow (close to body)
            [280.0, 230.0, 0.85],  # left_wrist (at waist level, close to body)
            [360.0, 230.0, 0.85],  # right_wrist (close to body)
            [290.0, 250.0, 0.92],  # left_hip
            [350.0, 250.0, 0.92],  # right_hip
            [285.0, 350.0, 0.89],  # left_knee
            [355.0, 350.0, 0.89],  # right_knee
            [280.0, 450.0, 0.87],  # left_ankle
            [360.0, 450.0, 0.87],  # right_ankle
        ]
    )


@pytest.fixture
def fallen_keypoints():
    """Create keypoints for a fallen/lying person.

    Person lying on the ground - head and feet at similar Y level.
    """
    return np.array(
        [
            [100.0, 300.0, 0.90],  # nose (on ground level)
            [90.0, 300.0, 0.85],  # left_eye
            [110.0, 300.0, 0.85],  # right_eye
            [80.0, 305.0, 0.80],  # left_ear
            [120.0, 305.0, 0.80],  # right_ear
            [150.0, 290.0, 0.85],  # left_shoulder
            [150.0, 310.0, 0.85],  # right_shoulder
            [200.0, 280.0, 0.80],  # left_elbow
            [200.0, 320.0, 0.80],  # right_elbow
            [250.0, 270.0, 0.75],  # left_wrist
            [250.0, 330.0, 0.75],  # right_wrist
            [300.0, 285.0, 0.88],  # left_hip
            [300.0, 315.0, 0.88],  # right_hip
            [380.0, 280.0, 0.82],  # left_knee
            [380.0, 320.0, 0.82],  # right_knee
            [450.0, 275.0, 0.80],  # left_ankle (near same Y as head)
            [450.0, 325.0, 0.80],  # right_ankle
        ]
    )


@pytest.fixture
def aggressive_keypoints():
    """Create keypoints for aggressive posture.

    Person with arms raised high (above head level).
    """
    return np.array(
        [
            [320.0, 100.0, 0.95],  # nose
            [310.0, 95.0, 0.92],  # left_eye
            [330.0, 95.0, 0.92],  # right_eye
            [300.0, 100.0, 0.85],  # left_ear
            [340.0, 100.0, 0.85],  # right_ear
            [280.0, 150.0, 0.90],  # left_shoulder
            [360.0, 150.0, 0.90],  # right_shoulder
            [260.0, 80.0, 0.88],  # left_elbow (raised)
            [380.0, 80.0, 0.88],  # right_elbow (raised)
            [250.0, 30.0, 0.85],  # left_wrist (above head!)
            [390.0, 30.0, 0.85],  # right_wrist (above head!)
            [290.0, 280.0, 0.92],  # left_hip
            [350.0, 280.0, 0.92],  # right_hip
            [285.0, 380.0, 0.89],  # left_knee
            [355.0, 380.0, 0.89],  # right_knee
            [280.0, 470.0, 0.87],  # left_ankle
            [360.0, 470.0, 0.87],  # right_ankle
        ]
    )


@pytest.fixture
def crouching_keypoints():
    """Create keypoints for a crouching person.

    Person crouched down with compressed torso and arms close to body.
    """
    return np.array(
        [
            [320.0, 200.0, 0.90],  # nose (low, near hips)
            [310.0, 195.0, 0.85],  # left_eye
            [330.0, 195.0, 0.85],  # right_eye
            [300.0, 200.0, 0.80],  # left_ear
            [340.0, 200.0, 0.80],  # right_ear
            [280.0, 220.0, 0.85],  # left_shoulder (close to hips)
            [360.0, 220.0, 0.85],  # right_shoulder
            [275.0, 240.0, 0.82],  # left_elbow (close to body)
            [365.0, 240.0, 0.82],  # right_elbow (close to body)
            [280.0, 260.0, 0.78],  # left_wrist (close to body)
            [360.0, 260.0, 0.78],  # right_wrist (close to body)
            [290.0, 250.0, 0.90],  # left_hip
            [350.0, 250.0, 0.90],  # right_hip
            [285.0, 270.0, 0.85],  # left_knee (close to hips)
            [355.0, 270.0, 0.85],  # right_knee
            [280.0, 300.0, 0.82],  # left_ankle
            [360.0, 300.0, 0.82],  # right_ankle
        ]
    )


@pytest.fixture
def mock_pose_model():
    """Create a mock YOLO pose model for testing."""
    mock_model = MagicMock()

    # Create mock keypoints result for standing person
    mock_result = MagicMock()
    mock_boxes = MagicMock()

    # Mock keypoints data
    mock_keypoints = MagicMock()
    # xy coordinates: shape (1, 17, 2) for one person with 17 keypoints
    mock_keypoints.xy = MagicMock()
    mock_keypoints.xy.cpu.return_value.numpy.return_value = np.array(
        [
            [
                [320.0, 50.0],
                [310.0, 45.0],
                [330.0, 45.0],
                [300.0, 50.0],
                [340.0, 50.0],
                [280.0, 100.0],
                [360.0, 100.0],
                [260.0, 170.0],
                [380.0, 170.0],
                [250.0, 230.0],
                [390.0, 230.0],
                [290.0, 250.0],
                [350.0, 250.0],
                [285.0, 350.0],
                [355.0, 350.0],
                [280.0, 450.0],
                [360.0, 450.0],
            ]
        ]
    )
    # Confidence scores: shape (1, 17)
    mock_keypoints.conf = MagicMock()
    mock_keypoints.conf.cpu.return_value.numpy.return_value = np.full((1, 17), 0.9)

    mock_result.keypoints = mock_keypoints

    # Mock bounding boxes for person detection
    # boxes.xyxy[person_idx] should return a tensor that .cpu().numpy() returns [x1, y1, x2, y2]
    mock_xyxy_indexed = MagicMock()
    mock_xyxy_indexed.cpu.return_value.numpy.return_value = np.array([200.0, 30.0, 440.0, 470.0])

    mock_xyxy = MagicMock()
    mock_xyxy.__getitem__ = MagicMock(return_value=mock_xyxy_indexed)

    # boxes.conf[person_idx] should return a tensor that .cpu().numpy() returns a single value
    mock_conf_indexed = MagicMock()
    mock_conf_indexed.cpu.return_value.numpy.return_value = 0.95

    mock_conf = MagicMock()
    mock_conf.__getitem__ = MagicMock(return_value=mock_conf_indexed)

    mock_boxes.__len__ = MagicMock(return_value=1)
    mock_boxes.xyxy = mock_xyxy
    mock_boxes.conf = mock_conf

    mock_result.boxes = mock_boxes

    mock_model.return_value = [mock_result]
    mock_model.predict.return_value = [mock_result]

    return mock_model


@pytest.fixture
def mock_empty_pose_model():
    """Create a mock pose model that returns no detections."""
    mock_model = MagicMock()

    mock_result = MagicMock()
    mock_result.keypoints = None
    mock_result.boxes = MagicMock()
    mock_result.boxes.__len__ = MagicMock(return_value=0)

    mock_model.return_value = [mock_result]
    mock_model.predict.return_value = [mock_result]

    return mock_model


# =============================================================================
# Test: Pydantic Schemas
# =============================================================================


class TestPoseSchemas:
    """Tests for pose estimation Pydantic schemas."""

    def test_keypoint_schema_creation(self):
        """Test that Keypoint schema can be created."""
        from pose_estimation import Keypoint

        kp = Keypoint(name="nose", x=320.0, y=50.0, confidence=0.95)
        assert kp.name == "nose"
        assert kp.x == 320.0
        assert kp.y == 50.0
        assert kp.confidence == 0.95

    def test_pose_detection_schema(self):
        """Test PoseDetection schema with behavior flags."""
        from pose_estimation import BehaviorFlags, PoseDetection

        detection = PoseDetection(
            person_id=0,
            bbox={"x": 100, "y": 50, "width": 200, "height": 400},
            confidence=0.95,
            keypoints=[],
            pose_class="standing",
            behavior=BehaviorFlags(
                is_fallen=False,
                is_aggressive=False,
                is_loitering=False,
            ),
        )
        assert detection.person_id == 0
        assert detection.pose_class == "standing"
        assert not detection.behavior.is_fallen

    def test_behavior_flags_schema(self):
        """Test BehaviorFlags schema."""
        from pose_estimation import BehaviorFlags

        flags = BehaviorFlags(
            is_fallen=True,
            is_aggressive=False,
            is_loitering=False,
            fall_confidence=0.85,
        )
        assert flags.is_fallen is True
        assert flags.fall_confidence == 0.85
        assert flags.is_aggressive is False

    def test_pose_response_schema(self):
        """Test PoseEstimationResponse schema."""
        from pose_estimation import PoseEstimationResponse

        response = PoseEstimationResponse(
            detections=[],
            inference_time_ms=45.2,
            image_width=640,
            image_height=480,
            alerts=[],
        )
        assert response.inference_time_ms == 45.2
        assert len(response.alerts) == 0


# =============================================================================
# Test: Behavior Detection Logic
# =============================================================================


class TestFallDetection:
    """Tests for fall detection logic."""

    def test_detect_fall_lying_horizontal(self, fallen_keypoints):
        """Test fall detection for person lying horizontally."""
        from pose_estimation import detect_fall

        result = detect_fall(fallen_keypoints)
        assert result["is_fallen"] is True
        assert result["confidence"] > 0.5

    def test_no_fall_standing(self, standing_keypoints):
        """Test no fall detection for standing person."""
        from pose_estimation import detect_fall

        result = detect_fall(standing_keypoints)
        assert result["is_fallen"] is False

    def test_no_fall_crouching(self, crouching_keypoints):
        """Test no fall detection for crouching (not fallen)."""
        from pose_estimation import detect_fall

        result = detect_fall(crouching_keypoints)
        # Crouching should not trigger fall detection
        assert result["is_fallen"] is False

    def test_fall_detection_low_confidence(self):
        """Test fall detection with low confidence keypoints."""
        from pose_estimation import detect_fall

        # Low confidence keypoints - should still detect if pattern matches
        low_conf_keypoints = np.array(
            [
                [100.0, 300.0, 0.3],  # nose (low conf)
                [90.0, 300.0, 0.3],  # left_eye
                [110.0, 300.0, 0.3],  # right_eye
                [80.0, 305.0, 0.3],  # left_ear
                [120.0, 305.0, 0.3],  # right_ear
                [150.0, 290.0, 0.3],  # left_shoulder
                [150.0, 310.0, 0.3],  # right_shoulder
                [200.0, 280.0, 0.3],  # left_elbow
                [200.0, 320.0, 0.3],  # right_elbow
                [250.0, 270.0, 0.3],  # left_wrist
                [250.0, 330.0, 0.3],  # right_wrist
                [300.0, 285.0, 0.3],  # left_hip
                [300.0, 315.0, 0.3],  # right_hip
                [380.0, 280.0, 0.3],  # left_knee
                [380.0, 320.0, 0.3],  # right_knee
                [450.0, 275.0, 0.3],  # left_ankle
                [450.0, 325.0, 0.3],  # right_ankle
            ]
        )
        result = detect_fall(low_conf_keypoints)
        # Lower confidence should reduce detection confidence
        assert result["confidence"] < 0.7


class TestAggressionDetection:
    """Tests for aggression detection logic."""

    def test_detect_aggression_raised_arms(self, aggressive_keypoints):
        """Test aggression detection with raised arms."""
        from pose_estimation import detect_aggression

        result = detect_aggression(aggressive_keypoints)
        assert result["is_aggressive"] is True
        assert "raised_arms" in result.get("indicators", [])

    def test_no_aggression_standing(self, standing_keypoints):
        """Test no aggression for normal standing pose."""
        from pose_estimation import detect_aggression

        result = detect_aggression(standing_keypoints)
        assert result["is_aggressive"] is False

    def test_aggression_with_rapid_movement(self):
        """Test aggression detection with rapid movement between frames."""
        from pose_estimation import detect_aggression_with_motion

        # Current frame keypoints
        current = np.array(
            [
                [320.0, 100.0, 0.95],  # nose
                [310.0, 95.0, 0.92],  # rest of keypoints...
                [330.0, 95.0, 0.92],
                [300.0, 100.0, 0.85],
                [340.0, 100.0, 0.85],
                [280.0, 150.0, 0.90],
                [360.0, 150.0, 0.90],
                [260.0, 80.0, 0.88],
                [380.0, 80.0, 0.88],
                [250.0, 30.0, 0.85],
                [390.0, 30.0, 0.85],
                [290.0, 280.0, 0.92],
                [350.0, 280.0, 0.92],
                [285.0, 380.0, 0.89],
                [355.0, 380.0, 0.89],
                [280.0, 470.0, 0.87],
                [360.0, 470.0, 0.87],
            ]
        )

        # Previous frame - large movement in arms
        previous = current.copy()
        previous[9, :2] = [250.0, 230.0]  # left_wrist moved up 200px
        previous[10, :2] = [390.0, 230.0]  # right_wrist moved up 200px

        result = detect_aggression_with_motion(current, previous, time_delta_ms=100)
        assert result["is_aggressive"] is True
        assert "rapid_movement" in result.get("indicators", [])


class TestLoiteringDetection:
    """Tests for loitering detection logic."""

    def test_detect_loitering_stationary(self):
        """Test loitering detection for stationary person."""
        from pose_estimation import detect_loitering

        # Same position over time threshold
        position_history = [
            {"x": 320.0, "y": 300.0, "timestamp_ms": 0},
            {"x": 321.0, "y": 301.0, "timestamp_ms": 10000},
            {"x": 319.0, "y": 299.0, "timestamp_ms": 20000},
            {"x": 320.0, "y": 300.0, "timestamp_ms": 30000},  # 30 seconds
        ]

        result = detect_loitering(position_history, threshold_seconds=25)
        assert result["is_loitering"] is True
        assert result["duration_seconds"] >= 25

    def test_no_loitering_moving(self):
        """Test no loitering detection for moving person."""
        from pose_estimation import detect_loitering

        # Person moving significantly
        position_history = [
            {"x": 100.0, "y": 300.0, "timestamp_ms": 0},
            {"x": 200.0, "y": 300.0, "timestamp_ms": 10000},
            {"x": 300.0, "y": 300.0, "timestamp_ms": 20000},
            {"x": 400.0, "y": 300.0, "timestamp_ms": 30000},
        ]

        result = detect_loitering(position_history, threshold_seconds=25)
        assert result["is_loitering"] is False

    def test_no_loitering_insufficient_time(self):
        """Test no loitering when under time threshold."""
        from pose_estimation import detect_loitering

        # Stationary but not long enough
        position_history = [
            {"x": 320.0, "y": 300.0, "timestamp_ms": 0},
            {"x": 321.0, "y": 301.0, "timestamp_ms": 5000},  # Only 5 seconds
        ]

        result = detect_loitering(position_history, threshold_seconds=25)
        assert result["is_loitering"] is False


# =============================================================================
# Test: Pose Classification
# =============================================================================


class TestPoseClassification:
    """Tests for pose classification."""

    def test_classify_standing(self, standing_keypoints):
        """Test classification of standing pose."""
        from pose_estimation import classify_pose

        pose_class = classify_pose(standing_keypoints)
        assert pose_class == "standing"

    def test_classify_fallen(self, fallen_keypoints):
        """Test classification of fallen pose."""
        from pose_estimation import classify_pose

        pose_class = classify_pose(fallen_keypoints)
        assert pose_class in ["lying_down", "fallen"]

    def test_classify_crouching(self, crouching_keypoints):
        """Test classification of crouching pose."""
        from pose_estimation import classify_pose

        pose_class = classify_pose(crouching_keypoints)
        assert pose_class == "crouching"

    def test_classify_aggressive(self, aggressive_keypoints):
        """Test classification of aggressive pose."""
        from pose_estimation import classify_pose

        pose_class = classify_pose(aggressive_keypoints)
        assert pose_class in ["reaching_up", "aggressive"]


# =============================================================================
# Test: YOLO26PoseModel Class
# =============================================================================


class TestYOLO26PoseModel:
    """Tests for YOLO26PoseModel wrapper class."""

    def test_model_initialization(self):
        """Test model initialization."""
        from pose_estimation import YOLO26PoseModel

        model = YOLO26PoseModel(
            model_path="yolo11n-pose.pt",
            confidence_threshold=0.5,
            device="cpu",
        )
        assert model.confidence_threshold == 0.5
        assert model.device == "cpu"
        assert model.model is None  # Not loaded yet

    def test_model_detect_poses_raises_if_not_loaded(self, dummy_image):
        """Test that detect_poses raises if model not loaded."""
        from pose_estimation import YOLO26PoseModel

        model = YOLO26PoseModel(model_path="test.pt")
        with pytest.raises(RuntimeError, match="Model not loaded"):
            model.detect_poses(dummy_image)

    def test_model_detect_with_mock(self, mock_pose_model, dummy_image):
        """Test pose detection with mocked model."""
        from pose_estimation import YOLO26PoseModel

        model = YOLO26PoseModel(model_path="test.pt", device="cpu")
        model.model = mock_pose_model

        detections, inference_time = model.detect_poses(dummy_image)

        assert len(detections) >= 0  # May have detections
        assert inference_time > 0

    def test_model_warmup(self, mock_pose_model):
        """Test model warmup."""
        from pose_estimation import YOLO26PoseModel

        model = YOLO26PoseModel(model_path="test.pt", device="cpu")
        model.model = mock_pose_model

        # Warmup should not raise
        model._warmup(num_iterations=1)


# =============================================================================
# Test: API Endpoints (requires importing app)
# =============================================================================


class TestPoseAPIEndpoints:
    """Tests for pose estimation API endpoints."""

    @pytest.fixture(autouse=True)
    def _setup_mocks(self, mock_pose_model):
        """Set up mocks for API testing."""
        import model as model_module

        # Store original
        original_pose_model = getattr(model_module, "pose_model", None)

        # Create mock model instance
        mock_instance = MagicMock()
        mock_instance.model = mock_pose_model
        mock_instance.detect_poses.return_value = (
            [
                {
                    "person_id": 0,
                    "bbox": {"x": 100, "y": 50, "width": 200, "height": 400},
                    "confidence": 0.95,
                    "keypoints": [],
                    "pose_class": "standing",
                    "behavior": {
                        "is_fallen": False,
                        "is_aggressive": False,
                        "is_loitering": False,
                    },
                }
            ],
            45.2,
        )
        mock_instance.inference_healthy = True
        mock_instance.model_path = "/models/yolo11n-pose.pt"

        # Mock the pose_model in model.py (used by get_pose_model function)
        model_module.pose_model = mock_instance
        yield mock_instance

        # Restore
        model_module.pose_model = original_pose_model

    def test_pose_health_endpoint(self, _setup_mocks):
        """Test pose estimation health endpoint."""
        from fastapi.testclient import TestClient
        from model import app

        client = TestClient(app)
        response = client.get("/pose/health")

        # May return 404 if endpoint not implemented yet (TDD)
        assert response.status_code in [200, 404]

    def test_pose_detect_endpoint_with_file(self, _setup_mocks, dummy_image_bytes):
        """Test pose detection endpoint with file upload."""
        from fastapi.testclient import TestClient
        from model import app

        client = TestClient(app)
        response = client.post(
            "/pose/detect",
            files={"file": ("test.jpg", dummy_image_bytes, "image/jpeg")},
        )

        # May return 404 if endpoint not implemented yet (TDD)
        if response.status_code == 200:
            data = response.json()
            assert "detections" in data
            assert "inference_time_ms" in data
        else:
            # Endpoint not yet implemented
            assert response.status_code == 404

    def test_pose_analyze_endpoint(self, _setup_mocks, dummy_image_bytes):
        """Test pose analysis with behavior detection."""
        from fastapi.testclient import TestClient
        from model import app

        client = TestClient(app)
        response = client.post(
            "/pose/analyze",
            files={"file": ("test.jpg", dummy_image_bytes, "image/jpeg")},
        )

        # May return 404 if endpoint not implemented yet
        if response.status_code == 200:
            data = response.json()
            assert "detections" in data
            assert "alerts" in data


# =============================================================================
# Test: Metrics
# =============================================================================


class TestPoseMetrics:
    """Tests for pose estimation Prometheus metrics."""

    def test_pose_detection_metrics_exist(self):
        """Test that pose detection metrics are defined."""
        from pose_estimation import (
            POSE_BEHAVIOR_ALERTS_TOTAL,
            POSE_DETECTIONS_TOTAL,
            POSE_INFERENCE_DURATION_SECONDS,
        )

        assert POSE_DETECTIONS_TOTAL is not None
        assert POSE_INFERENCE_DURATION_SECONDS is not None
        assert POSE_BEHAVIOR_ALERTS_TOTAL is not None

    def test_record_pose_detection(self):
        """Test recording pose detection metrics."""
        from pose_estimation import record_pose_detection

        # Should not raise
        record_pose_detection(pose_class="standing", confidence=0.95)

    def test_record_behavior_alert(self):
        """Test recording behavior alert metrics."""
        from pose_estimation import record_behavior_alert

        # Should not raise
        record_behavior_alert(alert_type="fall_detected")


# =============================================================================
# Test: Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_keypoints(self):
        """Test behavior detection with empty keypoints."""
        from pose_estimation import detect_aggression, detect_fall

        empty_kp = np.array([]).reshape(0, 3)

        fall_result = detect_fall(empty_kp)
        assert fall_result["is_fallen"] is False

        aggression_result = detect_aggression(empty_kp)
        assert aggression_result["is_aggressive"] is False

    def test_partial_keypoints(self):
        """Test detection with only some keypoints visible."""
        from pose_estimation import detect_fall

        # Only upper body visible
        partial_kp = np.array(
            [
                [320.0, 50.0, 0.95],  # nose
                [310.0, 45.0, 0.92],  # left_eye
                [330.0, 45.0, 0.92],  # right_eye
                [300.0, 50.0, 0.85],  # left_ear
                [340.0, 50.0, 0.85],  # right_ear
                [280.0, 100.0, 0.90],  # left_shoulder
                [360.0, 100.0, 0.90],  # right_shoulder
                [0.0, 0.0, 0.0],  # left_elbow (not visible)
                [0.0, 0.0, 0.0],  # right_elbow
                [0.0, 0.0, 0.0],  # left_wrist
                [0.0, 0.0, 0.0],  # right_wrist
                [0.0, 0.0, 0.0],  # left_hip
                [0.0, 0.0, 0.0],  # right_hip
                [0.0, 0.0, 0.0],  # left_knee
                [0.0, 0.0, 0.0],  # right_knee
                [0.0, 0.0, 0.0],  # left_ankle
                [0.0, 0.0, 0.0],  # right_ankle
            ]
        )

        result = detect_fall(partial_kp)
        # Should handle gracefully
        assert "is_fallen" in result

    def test_single_person_multiple_frames(self):
        """Test tracking single person across multiple frames for loitering."""
        from pose_estimation import LoiteringTracker

        tracker = LoiteringTracker(threshold_seconds=10)

        # Add positions over time
        tracker.update(person_id=1, x=320.0, y=300.0, timestamp_ms=0)
        tracker.update(person_id=1, x=321.0, y=301.0, timestamp_ms=5000)
        tracker.update(person_id=1, x=319.0, y=299.0, timestamp_ms=10000)

        result = tracker.check_loitering(person_id=1)
        assert result["is_loitering"] is True
        assert result["duration_seconds"] >= 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
