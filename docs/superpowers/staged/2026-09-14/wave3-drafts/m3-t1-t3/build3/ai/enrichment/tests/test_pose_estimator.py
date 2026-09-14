"""Unit tests for YOLOv8n-pose PoseEstimator.

Tests cover:
- Keypoint dataclass and constants
- PoseResult dataclass and suspicious pose flagging
- Model path validation
- Pose classification logic
- Confidence calculation
- Integration with model (mocked)
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PIL import Image

# Add the ai/enrichment directory to sys.path to enable imports
# This must happen before importing the local module
_enrichment_dir = Path(__file__).parent.parent
if str(_enrichment_dir) not in sys.path:
    sys.path.insert(0, str(_enrichment_dir))

from models.pose_estimator import (
    KEYPOINT_INDICES,
    KEYPOINT_NAMES,
    SUSPICIOUS_POSES,
    Keypoint,
    PoseEstimator,
    PoseResult,
    _get_tensorrt_enabled,
    _get_tensorrt_engine_path,
    _get_tensorrt_fp16_enabled,
    validate_model_path,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def dummy_image() -> Image.Image:
    """Create a dummy PIL image for testing."""
    return Image.new("RGB", (640, 480), color="red")


@pytest.fixture
def dummy_numpy_image() -> np.ndarray:
    """Create a dummy numpy image for testing."""
    return np.zeros((480, 640, 3), dtype=np.uint8)


@pytest.fixture
def sample_keypoints() -> list[Keypoint]:
    """Create sample keypoints for a standing person."""
    # Simulate a person standing upright (Y increases downward in images)
    return [
        Keypoint(name="nose", x=320.0, y=50.0, confidence=0.95),
        Keypoint(name="left_eye", x=310.0, y=45.0, confidence=0.92),
        Keypoint(name="right_eye", x=330.0, y=45.0, confidence=0.92),
        Keypoint(name="left_ear", x=300.0, y=50.0, confidence=0.85),
        Keypoint(name="right_ear", x=340.0, y=50.0, confidence=0.85),
        Keypoint(name="left_shoulder", x=280.0, y=100.0, confidence=0.90),
        Keypoint(name="right_shoulder", x=360.0, y=100.0, confidence=0.90),
        Keypoint(name="left_elbow", x=260.0, y=170.0, confidence=0.88),
        Keypoint(name="right_elbow", x=380.0, y=170.0, confidence=0.88),
        Keypoint(name="left_wrist", x=250.0, y=230.0, confidence=0.85),
        Keypoint(name="right_wrist", x=390.0, y=230.0, confidence=0.85),
        Keypoint(name="left_hip", x=290.0, y=250.0, confidence=0.92),
        Keypoint(name="right_hip", x=350.0, y=250.0, confidence=0.92),
        Keypoint(name="left_knee", x=285.0, y=350.0, confidence=0.89),
        Keypoint(name="right_knee", x=355.0, y=350.0, confidence=0.89),
        Keypoint(name="left_ankle", x=280.0, y=450.0, confidence=0.87),
        Keypoint(name="right_ankle", x=360.0, y=450.0, confidence=0.87),
    ]


@pytest.fixture
def crouching_keypoints() -> list[Keypoint]:
    """Create keypoints for a crouching person."""
    # Person bent down, nose close to hip level
    return [
        Keypoint(name="nose", x=320.0, y=200.0, confidence=0.95),  # Much lower
        Keypoint(name="left_eye", x=310.0, y=195.0, confidence=0.92),
        Keypoint(name="right_eye", x=330.0, y=195.0, confidence=0.92),
        Keypoint(name="left_ear", x=300.0, y=200.0, confidence=0.85),
        Keypoint(name="right_ear", x=340.0, y=200.0, confidence=0.85),
        Keypoint(name="left_shoulder", x=280.0, y=220.0, confidence=0.90),  # Close to hips
        Keypoint(name="right_shoulder", x=360.0, y=220.0, confidence=0.90),
        Keypoint(name="left_elbow", x=260.0, y=240.0, confidence=0.88),
        Keypoint(name="right_elbow", x=380.0, y=240.0, confidence=0.88),
        Keypoint(name="left_wrist", x=250.0, y=260.0, confidence=0.85),
        Keypoint(name="right_wrist", x=390.0, y=260.0, confidence=0.85),
        Keypoint(name="left_hip", x=290.0, y=250.0, confidence=0.92),
        Keypoint(name="right_hip", x=350.0, y=250.0, confidence=0.92),
        Keypoint(name="left_knee", x=285.0, y=270.0, confidence=0.89),  # Close to hips
        Keypoint(name="right_knee", x=355.0, y=270.0, confidence=0.89),
        Keypoint(name="left_ankle", x=280.0, y=300.0, confidence=0.87),
        Keypoint(name="right_ankle", x=360.0, y=300.0, confidence=0.87),
    ]


@pytest.fixture
def reaching_up_keypoints() -> list[Keypoint]:
    """Create keypoints for a person reaching up."""
    return [
        Keypoint(name="nose", x=320.0, y=100.0, confidence=0.95),
        Keypoint(name="left_eye", x=310.0, y=95.0, confidence=0.92),
        Keypoint(name="right_eye", x=330.0, y=95.0, confidence=0.92),
        Keypoint(name="left_ear", x=300.0, y=100.0, confidence=0.85),
        Keypoint(name="right_ear", x=340.0, y=100.0, confidence=0.85),
        Keypoint(name="left_shoulder", x=280.0, y=150.0, confidence=0.90),
        Keypoint(name="right_shoulder", x=360.0, y=150.0, confidence=0.90),
        Keypoint(name="left_elbow", x=270.0, y=100.0, confidence=0.88),
        Keypoint(name="right_elbow", x=370.0, y=100.0, confidence=0.88),
        Keypoint(name="left_wrist", x=265.0, y=30.0, confidence=0.85),  # Above head
        Keypoint(name="right_wrist", x=375.0, y=30.0, confidence=0.85),  # Above head
        Keypoint(name="left_hip", x=290.0, y=280.0, confidence=0.92),
        Keypoint(name="right_hip", x=350.0, y=280.0, confidence=0.92),
        Keypoint(name="left_knee", x=285.0, y=380.0, confidence=0.89),
        Keypoint(name="right_knee", x=355.0, y=380.0, confidence=0.89),
        Keypoint(name="left_ankle", x=280.0, y=470.0, confidence=0.87),
        Keypoint(name="right_ankle", x=360.0, y=470.0, confidence=0.87),
    ]


@pytest.fixture
def running_keypoints() -> list[Keypoint]:
    """Create keypoints for a running person."""
    # Wide leg spread indicating running stride
    return [
        Keypoint(name="nose", x=320.0, y=50.0, confidence=0.95),
        Keypoint(name="left_eye", x=310.0, y=45.0, confidence=0.92),
        Keypoint(name="right_eye", x=330.0, y=45.0, confidence=0.92),
        Keypoint(name="left_ear", x=300.0, y=50.0, confidence=0.85),
        Keypoint(name="right_ear", x=340.0, y=50.0, confidence=0.85),
        Keypoint(name="left_shoulder", x=280.0, y=100.0, confidence=0.90),
        Keypoint(name="right_shoulder", x=360.0, y=100.0, confidence=0.90),
        Keypoint(name="left_elbow", x=250.0, y=170.0, confidence=0.88),
        Keypoint(name="right_elbow", x=390.0, y=170.0, confidence=0.88),
        Keypoint(name="left_wrist", x=230.0, y=230.0, confidence=0.85),
        Keypoint(name="right_wrist", x=410.0, y=230.0, confidence=0.85),
        Keypoint(name="left_hip", x=290.0, y=250.0, confidence=0.92),
        Keypoint(name="right_hip", x=350.0, y=250.0, confidence=0.92),
        Keypoint(name="left_knee", x=200.0, y=350.0, confidence=0.89),
        Keypoint(name="right_knee", x=440.0, y=350.0, confidence=0.89),
        Keypoint(name="left_ankle", x=150.0, y=450.0, confidence=0.87),  # Wide spread
        Keypoint(name="right_ankle", x=490.0, y=450.0, confidence=0.87),  # Wide spread
    ]


@pytest.fixture
def mock_yolo_model():
    """Create a mock YOLO model."""
    mock_model = MagicMock()

    # Create mock keypoints result
    mock_keypoints = MagicMock()
    mock_keypoints.xy = [
        MagicMock(
            cpu=MagicMock(
                return_value=MagicMock(
                    numpy=MagicMock(
                        return_value=np.array(
                            [
                                [320.0, 50.0],  # nose
                                [310.0, 45.0],  # left_eye
                                [330.0, 45.0],  # right_eye
                                [300.0, 50.0],  # left_ear
                                [340.0, 50.0],  # right_ear
                                [280.0, 100.0],  # left_shoulder
                                [360.0, 100.0],  # right_shoulder
                                [260.0, 170.0],  # left_elbow
                                [380.0, 170.0],  # right_elbow
                                [250.0, 230.0],  # left_wrist
                                [390.0, 230.0],  # right_wrist
                                [290.0, 250.0],  # left_hip
                                [350.0, 250.0],  # right_hip
                                [285.0, 350.0],  # left_knee
                                [355.0, 350.0],  # right_knee
                                [280.0, 450.0],  # left_ankle
                                [360.0, 450.0],  # right_ankle
                            ]
                        )
                    )
                )
            )
        )
    ]
    mock_keypoints.conf = [
        MagicMock(
            cpu=MagicMock(return_value=MagicMock(numpy=MagicMock(return_value=np.full(17, 0.9))))
        )
    ]

    # Create mock result
    mock_result = MagicMock()
    mock_result.keypoints = [mock_keypoints]

    # Configure model call
    mock_model.return_value = [mock_result]
    mock_model.to = MagicMock(return_value=mock_model)

    return mock_model


@pytest.fixture
def mock_pose_estimator(mock_yolo_model):
    """Create a PoseEstimator with mocked YOLO model."""
    # Patch ultralytics.YOLO which is imported inside load_model()
    with (
        patch("ultralytics.YOLO", return_value=mock_yolo_model),
        patch("torch.cuda.is_available", return_value=False),
    ):
        estimator = PoseEstimator("/fake/model.pt", device="cpu")
        estimator.load_model()
        yield estimator


# =============================================================================
# Test: Keypoint Constants
# =============================================================================


class TestKeypointConstants:
    """Tests for keypoint-related constants."""

    def test_keypoint_names_count(self):
        """Test that we have exactly 17 COCO keypoints."""
        assert len(KEYPOINT_NAMES) == 17

    def test_keypoint_names_content(self):
        """Test that all expected keypoint names are present."""
        expected_names = {
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
        }
        assert set(KEYPOINT_NAMES) == expected_names

    def test_keypoint_indices_match_names(self):
        """Test that keypoint indices match their position in names list."""
        for idx, name in enumerate(KEYPOINT_NAMES):
            assert KEYPOINT_INDICES[name] == idx


# =============================================================================
# Test: Suspicious Poses
# =============================================================================


class TestSuspiciousPoses:
    """Tests for suspicious pose constants."""

    def test_suspicious_poses_content(self):
        """Test that expected suspicious poses are defined."""
        expected_suspicious = {"crouching", "crawling", "hiding", "reaching_up"}
        assert expected_suspicious == SUSPICIOUS_POSES

    def test_standing_is_not_suspicious(self):
        """Test that standing is not a suspicious pose."""
        assert "standing" not in SUSPICIOUS_POSES

    def test_running_is_not_suspicious(self):
        """Test that running is not a suspicious pose."""
        assert "running" not in SUSPICIOUS_POSES


# =============================================================================
# Test: Keypoint Dataclass
# =============================================================================


class TestKeypointDataclass:
    """Tests for the Keypoint dataclass."""

    def test_keypoint_creation(self):
        """Test creating a Keypoint instance."""
        kp = Keypoint(name="nose", x=320.0, y=240.0, confidence=0.95)
        assert kp.name == "nose"
        assert kp.x == 320.0
        assert kp.y == 240.0
        assert kp.confidence == 0.95

    def test_keypoint_equality(self):
        """Test that identical keypoints are equal."""
        kp1 = Keypoint(name="nose", x=320.0, y=240.0, confidence=0.95)
        kp2 = Keypoint(name="nose", x=320.0, y=240.0, confidence=0.95)
        assert kp1 == kp2


# =============================================================================
# Test: PoseResult Dataclass
# =============================================================================


class TestPoseResultDataclass:
    """Tests for the PoseResult dataclass."""

    def test_pose_result_standing(self, sample_keypoints):
        """Test PoseResult for standing pose."""
        result = PoseResult(
            keypoints=sample_keypoints,
            pose_class="standing",
            confidence=0.89,
            is_suspicious=False,
        )
        assert result.pose_class == "standing"
        assert not result.is_suspicious
        assert len(result.keypoints) == 17

    def test_pose_result_crouching_is_suspicious(self, sample_keypoints):
        """Test that crouching pose is flagged as suspicious."""
        result = PoseResult(
            keypoints=sample_keypoints,
            pose_class="crouching",
            confidence=0.85,
            is_suspicious=True,
        )
        assert result.pose_class == "crouching"
        assert result.is_suspicious

    def test_pose_result_unknown(self):
        """Test PoseResult for unknown/undetected pose."""
        result = PoseResult(
            keypoints=[],
            pose_class="unknown",
            confidence=0.0,
            is_suspicious=False,
        )
        assert result.pose_class == "unknown"
        assert result.confidence == 0.0
        assert not result.is_suspicious


# =============================================================================
# Test: Model Path Validation
# =============================================================================


class TestModelPathValidation:
    """Tests for model path validation security."""

    def test_valid_local_path(self):
        """Test that valid local paths are accepted."""
        path = validate_model_path("/models/yolov8n-pose.pt")
        assert path.startswith("/")

    def test_valid_relative_path(self):
        """Test that valid relative paths are accepted."""
        path = validate_model_path("./models/pose.pt")
        assert path  # Returns resolved path

    def test_valid_model_name(self):
        """Test that model names (non-paths) are accepted."""
        path = validate_model_path("yolov8n-pose.pt")
        assert path == "yolov8n-pose.pt"

    def test_rejects_path_traversal(self):
        """Test that path traversal is rejected."""
        with pytest.raises(ValueError, match="path traversal"):
            validate_model_path("/models/../../../etc/passwd")

    def test_rejects_embedded_traversal(self):
        """Test that embedded traversal sequences are rejected."""
        with pytest.raises(ValueError, match="path traversal"):
            validate_model_path("/models/subdir/../../../etc/passwd")


# =============================================================================
# Test: PoseEstimator Initialization
# =============================================================================


class TestPoseEstimatorInit:
    """Tests for PoseEstimator initialization."""

    def test_init_with_valid_path(self):
        """Test initialization with valid model path."""
        estimator = PoseEstimator("/models/pose.pt", device="cpu")
        assert estimator.model_path == "/models/pose.pt"
        assert estimator.device == "cpu"
        assert estimator.model is None

    def test_init_with_cuda_device(self):
        """Test initialization with CUDA device."""
        estimator = PoseEstimator("/models/pose.pt", device="cuda:0")
        assert estimator.device == "cuda:0"

    def test_init_rejects_path_traversal(self):
        """Test that initialization rejects path traversal."""
        with pytest.raises(ValueError, match="path traversal"):
            PoseEstimator("../../../etc/passwd")


# =============================================================================
# Test: Pose Classification Logic
# =============================================================================


class TestPoseClassification:
    """Tests for pose classification logic."""

    def test_classify_standing(self, mock_pose_estimator, sample_keypoints):
        """Test classification of standing pose."""
        pose_class = mock_pose_estimator._classify_pose(sample_keypoints)
        assert pose_class == "standing"

    def test_classify_crouching(self, mock_pose_estimator, crouching_keypoints):
        """Test classification of crouching pose."""
        pose_class = mock_pose_estimator._classify_pose(crouching_keypoints)
        assert pose_class == "crouching"

    def test_classify_reaching_up(self, mock_pose_estimator, reaching_up_keypoints):
        """Test classification of reaching up pose."""
        pose_class = mock_pose_estimator._classify_pose(reaching_up_keypoints)
        assert pose_class == "reaching_up"

    def test_classify_running(self, mock_pose_estimator, running_keypoints):
        """Test classification of running pose."""
        pose_class = mock_pose_estimator._classify_pose(running_keypoints)
        assert pose_class == "running"

    def test_classify_empty_keypoints(self, mock_pose_estimator):
        """Test classification with no keypoints returns unknown."""
        pose_class = mock_pose_estimator._classify_pose([])
        assert pose_class == "unknown"

    def test_classify_missing_hips_returns_unknown(self, mock_pose_estimator):
        """Test classification with missing hip keypoints returns unknown."""
        keypoints = [
            Keypoint(name="nose", x=320.0, y=50.0, confidence=0.95),
            Keypoint(name="left_shoulder", x=280.0, y=100.0, confidence=0.90),
        ]
        pose_class = mock_pose_estimator._classify_pose(keypoints)
        assert pose_class == "unknown"


# =============================================================================
# Test: Confidence Calculation
# =============================================================================


class TestConfidenceCalculation:
    """Tests for pose confidence calculation."""

    def test_calculate_confidence_normal(self, mock_pose_estimator, sample_keypoints):
        """Test confidence calculation with normal keypoints."""
        confidence = mock_pose_estimator._calculate_confidence(sample_keypoints)
        # All keypoints have confidence 0.85-0.95, average should be around 0.89
        assert 0.85 <= confidence <= 0.95

    def test_calculate_confidence_empty(self, mock_pose_estimator):
        """Test confidence calculation with empty keypoints."""
        confidence = mock_pose_estimator._calculate_confidence([])
        assert confidence == 0.0

    def test_calculate_confidence_single_keypoint(self, mock_pose_estimator):
        """Test confidence calculation with single keypoint."""
        keypoints = [Keypoint(name="nose", x=320.0, y=50.0, confidence=0.75)]
        confidence = mock_pose_estimator._calculate_confidence(keypoints)
        assert confidence == 0.75


# =============================================================================
# Test: Full Estimation Pipeline
# =============================================================================


class TestEstimationPipeline:
    """Tests for the full pose estimation pipeline."""

    def test_estimate_pose_returns_pose_result(self, mock_pose_estimator, dummy_image):
        """Test that estimate_pose returns a PoseResult."""
        result = mock_pose_estimator.estimate_pose(dummy_image)
        assert isinstance(result, PoseResult)

    def test_estimate_pose_with_numpy_array(self, mock_pose_estimator, dummy_numpy_image):
        """Test estimation with numpy array input."""
        result = mock_pose_estimator.estimate_pose(dummy_numpy_image)
        assert isinstance(result, PoseResult)

    def test_estimate_pose_with_bbox(self, mock_pose_estimator, dummy_image):
        """Test estimation with bounding box crop."""
        bbox = (100.0, 50.0, 500.0, 400.0)
        result = mock_pose_estimator.estimate_pose(dummy_image, bbox=bbox)
        assert isinstance(result, PoseResult)

    def test_estimate_pose_without_loaded_model(self, dummy_image):
        """Test that estimation fails if model not loaded."""
        estimator = PoseEstimator("/fake/model.pt", device="cpu")
        with pytest.raises(RuntimeError, match="Model not loaded"):
            estimator.estimate_pose(dummy_image)

    def test_estimate_pose_suspicious_flag(self, mock_pose_estimator, dummy_image):
        """Test that suspicious poses are flagged correctly."""
        result = mock_pose_estimator.estimate_pose(dummy_image)
        # Standing pose should not be suspicious
        if result.pose_class == "standing":
            assert not result.is_suspicious
        # If it were crouching, it should be suspicious
        if result.pose_class in SUSPICIOUS_POSES:
            assert result.is_suspicious


# =============================================================================
# Test: Model Loading/Unloading
# =============================================================================


class TestModelLifecycle:
    """Tests for model loading and unloading."""

    def test_load_model_sets_model(self, mock_yolo_model):
        """Test that load_model sets the model attribute."""
        with (
            patch("ultralytics.YOLO", return_value=mock_yolo_model),
            patch("torch.cuda.is_available", return_value=False),
        ):
            estimator = PoseEstimator("/fake/model.pt", device="cpu")
            result = estimator.load_model()
            assert estimator.model is not None
            assert result is estimator  # Returns self

    def test_unload_model_clears_model(self, mock_pose_estimator):
        """Test that unload clears the model."""
        assert mock_pose_estimator.model is not None
        mock_pose_estimator.unload()
        assert mock_pose_estimator.model is None


# =============================================================================
# Test: Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_bbox_clamping(self, mock_pose_estimator, dummy_image):
        """Test that bbox coordinates are clamped to image bounds."""
        # Bbox extends beyond image boundaries
        bbox = (-50.0, -50.0, 700.0, 600.0)
        result = mock_pose_estimator.estimate_pose(dummy_image, bbox=bbox)
        assert isinstance(result, PoseResult)

    def test_invalid_bbox_handled(self, mock_pose_estimator, dummy_image):
        """Test that invalid bbox (x2 < x1) is handled."""
        bbox = (500.0, 400.0, 100.0, 50.0)  # Inverted
        result = mock_pose_estimator.estimate_pose(dummy_image, bbox=bbox)
        assert isinstance(result, PoseResult)

    def test_small_image(self, mock_pose_estimator):
        """Test estimation with very small image."""
        small_image = Image.new("RGB", (32, 32), color="blue")
        result = mock_pose_estimator.estimate_pose(small_image)
        assert isinstance(result, PoseResult)

    def test_grayscale_image_converted(self, mock_pose_estimator):
        """Test that grayscale images are converted to RGB."""
        gray_image = Image.new("L", (640, 480), color=128)
        result = mock_pose_estimator.estimate_pose(gray_image)
        assert isinstance(result, PoseResult)


# =============================================================================
# Test: TensorRT Support (NEM-3838)
# =============================================================================


class TestTensorRTSupport:
    """Tests for TensorRT acceleration support."""

    def test_tensorrt_disabled_by_default(self, mock_yolo_model):
        """Test that TensorRT is disabled by default."""
        with (
            patch("ultralytics.YOLO", return_value=mock_yolo_model),
            patch("torch.cuda.is_available", return_value=False),
            patch.dict("os.environ", {}, clear=True),
        ):
            estimator = PoseEstimator("/fake/model.pt", device="cpu")
            assert estimator._use_tensorrt_requested is False
            assert estimator.use_tensorrt is False

    def test_tensorrt_enabled_via_env_var(self, mock_yolo_model):
        """Test TensorRT can be enabled via environment variable."""
        with (
            patch("ultralytics.YOLO", return_value=mock_yolo_model),
            patch("torch.cuda.is_available", return_value=False),
            patch.dict("os.environ", {"POSE_USE_TENSORRT": "true"}),
        ):
            estimator = PoseEstimator("/fake/model.pt", device="cpu")
            assert estimator._use_tensorrt_requested is True

    def test_tensorrt_enabled_via_parameter(self, mock_yolo_model):
        """Test TensorRT can be enabled via constructor parameter."""
        with (
            patch("ultralytics.YOLO", return_value=mock_yolo_model),
            patch("torch.cuda.is_available", return_value=False),
        ):
            estimator = PoseEstimator("/fake/model.pt", device="cpu", use_tensorrt=True)
            assert estimator._use_tensorrt_requested is True

    def test_tensorrt_parameter_overrides_env_var(self, mock_yolo_model):
        """Test that constructor parameter overrides environment variable."""
        with (
            patch("ultralytics.YOLO", return_value=mock_yolo_model),
            patch("torch.cuda.is_available", return_value=False),
            patch.dict("os.environ", {"POSE_USE_TENSORRT": "true"}),
        ):
            # Parameter False should override env var True
            estimator = PoseEstimator("/fake/model.pt", device="cpu", use_tensorrt=False)
            assert estimator._use_tensorrt_requested is False

    def test_tensorrt_fallback_when_unavailable(self, mock_yolo_model):
        """Test fallback to PyTorch when TensorRT is not available."""
        with (
            patch("ultralytics.YOLO", return_value=mock_yolo_model),
            patch("torch.cuda.is_available", return_value=False),
        ):
            estimator = PoseEstimator("/fake/model.pt", device="cpu", use_tensorrt=True)
            estimator.load_model()
            # Should fall back to PyTorch since CUDA is not available
            assert estimator.use_tensorrt is False
            assert estimator.model is not None

    def test_get_backend_info_pytorch(self, mock_yolo_model):
        """Test get_backend_info returns correct info for PyTorch."""
        with (
            patch("ultralytics.YOLO", return_value=mock_yolo_model),
            patch("torch.cuda.is_available", return_value=False),
        ):
            estimator = PoseEstimator("/fake/model.pt", device="cpu")
            estimator.load_model()

            info = estimator.get_backend_info()
            assert info["backend"] == "pytorch"
            assert info["tensorrt_active"] is False
            assert info["model_loaded"] is True

    def test_tensorrt_env_var_case_insensitive(self, mock_yolo_model):
        """Test POSE_USE_TENSORRT accepts various true values."""
        true_values = ["true", "TRUE", "True", "1", "yes", "YES"]
        for value in true_values:
            with (
                patch("ultralytics.YOLO", return_value=mock_yolo_model),
                patch("torch.cuda.is_available", return_value=False),
                patch.dict("os.environ", {"POSE_USE_TENSORRT": value}),
            ):
                estimator = PoseEstimator("/fake/model.pt", device="cpu")
                assert estimator._use_tensorrt_requested is True, f"Failed for value: {value}"

    def test_unload_resets_tensorrt_flag(self, mock_yolo_model):
        """Test that unload resets the use_tensorrt flag."""
        with (
            patch("ultralytics.YOLO", return_value=mock_yolo_model),
            patch("torch.cuda.is_available", return_value=False),
        ):
            estimator = PoseEstimator("/fake/model.pt", device="cpu")
            estimator.load_model()
            estimator.unload()
            assert estimator.use_tensorrt is False


class TestTensorRTEnginePathHelpers:
    """Tests for TensorRT engine path helper functions."""

    def test_engine_path_replaces_pt_extension(self):
        """Test that .pt extension is replaced with .engine."""
        with patch.dict("os.environ", {}, clear=True):
            path = _get_tensorrt_engine_path("/models/yolov8n-pose.pt")
            assert path == "/models/yolov8n-pose.engine"

    def test_engine_path_custom_env_var(self):
        """Test that custom engine path from env var is used."""
        with patch.dict("os.environ", {"POSE_TENSORRT_ENGINE_PATH": "/custom/path.engine"}):
            path = _get_tensorrt_engine_path("/models/yolov8n-pose.pt")
            assert path == "/custom/path.engine"

    def test_tensorrt_enabled_env_var(self):
        """Test _get_tensorrt_enabled function."""
        with patch.dict("os.environ", {"POSE_USE_TENSORRT": "false"}):
            assert _get_tensorrt_enabled() is False

        with patch.dict("os.environ", {"POSE_USE_TENSORRT": "true"}):
            assert _get_tensorrt_enabled() is True

    def test_tensorrt_fp16_enabled_default(self):
        """Test _get_tensorrt_fp16_enabled defaults to True."""
        with patch.dict("os.environ", {}, clear=True):
            assert _get_tensorrt_fp16_enabled() is True

    def test_tensorrt_fp16_can_be_disabled(self):
        """Test _get_tensorrt_fp16_enabled can be disabled."""
        with patch.dict("os.environ", {"POSE_TENSORRT_FP16": "false"}):
            assert _get_tensorrt_fp16_enabled() is False
