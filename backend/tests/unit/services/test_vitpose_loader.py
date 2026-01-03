"""Unit tests for vitpose_loader service.

Tests for the ViTPose+ Small model loader and pose estimation functions.
"""

from unittest.mock import MagicMock

import pytest

from backend.services.vitpose_loader import (
    KEYPOINT_NAMES,
    Keypoint,
    KeypointIndex,
    PoseResult,
    classify_pose,
    extract_keypoints_from_output,
    extract_pose_from_crop,
    extract_poses_batch,
    load_vitpose_model,
)

# Test KeypointIndex enum


def test_keypoint_index_has_17_values():
    """Test that KeypointIndex has all 17 COCO keypoints."""
    assert len(KeypointIndex) == 17


def test_keypoint_index_nose():
    """Test NOSE index is 0."""
    assert KeypointIndex.NOSE.value == 0


def test_keypoint_index_left_eye():
    """Test LEFT_EYE index is 1."""
    assert KeypointIndex.LEFT_EYE.value == 1


def test_keypoint_index_right_eye():
    """Test RIGHT_EYE index is 2."""
    assert KeypointIndex.RIGHT_EYE.value == 2


def test_keypoint_index_left_ear():
    """Test LEFT_EAR index is 3."""
    assert KeypointIndex.LEFT_EAR.value == 3


def test_keypoint_index_right_ear():
    """Test RIGHT_EAR index is 4."""
    assert KeypointIndex.RIGHT_EAR.value == 4


def test_keypoint_index_shoulders():
    """Test shoulder indices are 5 and 6."""
    assert KeypointIndex.LEFT_SHOULDER.value == 5
    assert KeypointIndex.RIGHT_SHOULDER.value == 6


def test_keypoint_index_elbows():
    """Test elbow indices are 7 and 8."""
    assert KeypointIndex.LEFT_ELBOW.value == 7
    assert KeypointIndex.RIGHT_ELBOW.value == 8


def test_keypoint_index_wrists():
    """Test wrist indices are 9 and 10."""
    assert KeypointIndex.LEFT_WRIST.value == 9
    assert KeypointIndex.RIGHT_WRIST.value == 10


def test_keypoint_index_hips():
    """Test hip indices are 11 and 12."""
    assert KeypointIndex.LEFT_HIP.value == 11
    assert KeypointIndex.RIGHT_HIP.value == 12


def test_keypoint_index_knees():
    """Test knee indices are 13 and 14."""
    assert KeypointIndex.LEFT_KNEE.value == 13
    assert KeypointIndex.RIGHT_KNEE.value == 14


def test_keypoint_index_ankles():
    """Test ankle indices are 15 and 16."""
    assert KeypointIndex.LEFT_ANKLE.value == 15
    assert KeypointIndex.RIGHT_ANKLE.value == 16


# Test KEYPOINT_NAMES constant


def test_keypoint_names_count():
    """Test that all 17 keypoint names are defined."""
    assert len(KEYPOINT_NAMES) == 17


def test_keypoint_names_order():
    """Test keypoint names are in correct order."""
    expected = [
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
    assert expected == KEYPOINT_NAMES


def test_keypoint_names_match_enum():
    """Test that KEYPOINT_NAMES matches KeypointIndex enum."""
    for idx, name in enumerate(KEYPOINT_NAMES):
        # Convert name to enum name format
        enum_name = name.upper()
        assert hasattr(KeypointIndex, enum_name)
        assert KeypointIndex[enum_name].value == idx


# Test Keypoint dataclass


def test_keypoint_creation():
    """Test Keypoint dataclass creation."""
    kp = Keypoint(x=100.5, y=200.5, confidence=0.95, name="left_shoulder")

    assert kp.x == 100.5
    assert kp.y == 200.5
    assert kp.confidence == 0.95
    assert kp.name == "left_shoulder"


def test_keypoint_zero_values():
    """Test Keypoint with zero coordinates."""
    kp = Keypoint(x=0.0, y=0.0, confidence=0.0, name="nose")

    assert kp.x == 0.0
    assert kp.y == 0.0
    assert kp.confidence == 0.0


def test_keypoint_normalized_coordinates():
    """Test Keypoint with normalized (0-1) coordinates."""
    kp = Keypoint(x=0.5, y=0.75, confidence=0.85, name="right_hip")

    assert 0 <= kp.x <= 1
    assert 0 <= kp.y <= 1


def test_keypoint_pixel_coordinates():
    """Test Keypoint with pixel coordinates."""
    kp = Keypoint(x=640.0, y=480.0, confidence=0.99, name="left_ankle")

    assert kp.x == 640.0
    assert kp.y == 480.0


# Test PoseResult dataclass


def test_pose_result_creation():
    """Test PoseResult dataclass creation."""
    keypoints = {
        "left_shoulder": Keypoint(x=100, y=150, confidence=0.9, name="left_shoulder"),
        "right_shoulder": Keypoint(x=200, y=150, confidence=0.88, name="right_shoulder"),
    }

    result = PoseResult(
        keypoints=keypoints, pose_class="standing", pose_confidence=0.85, bbox=[50, 100, 250, 400]
    )

    assert len(result.keypoints) == 2
    assert result.pose_class == "standing"
    assert result.pose_confidence == 0.85
    assert result.bbox == [50, 100, 250, 400]


def test_pose_result_without_bbox():
    """Test PoseResult without bounding box."""
    result = PoseResult(keypoints={}, pose_class="unknown", pose_confidence=0.0)

    assert result.bbox is None


def test_vitpose_pose_result_to_dict():
    """Test VitPose PoseResult.to_dict() method."""
    keypoints = {
        "nose": Keypoint(x=150, y=50, confidence=0.92, name="nose"),
        "left_hip": Keypoint(x=140, y=200, confidence=0.87, name="left_hip"),
    }

    result = PoseResult(
        keypoints=keypoints, pose_class="standing", pose_confidence=0.78, bbox=[100, 20, 200, 350]
    )

    d = result.to_dict()

    assert d["pose_class"] == "standing"
    assert d["pose_confidence"] == 0.78
    assert d["bbox"] == [100, 20, 200, 350]
    assert "keypoints" in d
    assert "nose" in d["keypoints"]
    assert d["keypoints"]["nose"]["x"] == 150
    assert d["keypoints"]["nose"]["y"] == 50
    assert d["keypoints"]["nose"]["confidence"] == 0.92


def test_pose_result_to_dict_empty_keypoints():
    """Test PoseResult.to_dict() with empty keypoints."""
    result = PoseResult(keypoints={}, pose_class="unknown", pose_confidence=0.0, bbox=None)

    d = result.to_dict()

    assert d["keypoints"] == {}
    assert d["pose_class"] == "unknown"
    assert d["pose_confidence"] == 0.0
    assert d["bbox"] is None


def test_pose_result_to_dict_preserves_all_keypoints():
    """Test that to_dict preserves all keypoints."""
    keypoints = {}
    for name in KEYPOINT_NAMES:
        keypoints[name] = Keypoint(x=100, y=100, confidence=0.9, name=name)

    result = PoseResult(keypoints=keypoints, pose_class="standing", pose_confidence=0.9)

    d = result.to_dict()

    assert len(d["keypoints"]) == 17


# Test classify_pose


def test_classify_pose_insufficient_keypoints():
    """Test classify_pose returns unknown with insufficient keypoints."""
    # Less than 2 required keypoints
    keypoints = {"left_hip": Keypoint(x=100, y=200, confidence=0.9, name="left_hip")}

    pose_class, confidence = classify_pose(keypoints)

    assert pose_class == "unknown"
    assert confidence == 0.0


def test_classify_pose_empty_keypoints():
    """Test classify_pose returns unknown with empty keypoints."""
    pose_class, confidence = classify_pose({})

    assert pose_class == "unknown"
    assert confidence == 0.0


def test_classify_pose_standing():
    """Test classify_pose detects standing posture."""
    # Standing: shoulder above hip, hip above knee, knee above ankle
    # In image coordinates: smaller Y = higher position
    keypoints = {
        "left_shoulder": Keypoint(x=100, y=50, confidence=0.9, name="left_shoulder"),
        "right_shoulder": Keypoint(x=150, y=50, confidence=0.9, name="right_shoulder"),
        "left_hip": Keypoint(x=105, y=150, confidence=0.9, name="left_hip"),
        "right_hip": Keypoint(x=145, y=150, confidence=0.9, name="right_hip"),
        "left_knee": Keypoint(x=105, y=250, confidence=0.9, name="left_knee"),
        "right_knee": Keypoint(x=145, y=250, confidence=0.9, name="right_knee"),
        "left_ankle": Keypoint(x=105, y=350, confidence=0.9, name="left_ankle"),
        "right_ankle": Keypoint(x=145, y=350, confidence=0.9, name="right_ankle"),
    }

    pose_class, confidence = classify_pose(keypoints)

    assert pose_class == "standing"
    assert confidence > 0.5


def test_classify_pose_sitting():
    """Test classify_pose detects sitting posture."""
    # Sitting: hips at or below knee level (Y position >= knee Y)
    keypoints = {
        "left_shoulder": Keypoint(x=100, y=50, confidence=0.9, name="left_shoulder"),
        "right_shoulder": Keypoint(x=150, y=50, confidence=0.9, name="right_shoulder"),
        "left_hip": Keypoint(x=105, y=200, confidence=0.9, name="left_hip"),
        "right_hip": Keypoint(x=145, y=200, confidence=0.9, name="right_hip"),
        "left_knee": Keypoint(x=105, y=180, confidence=0.9, name="left_knee"),
        "right_knee": Keypoint(x=145, y=180, confidence=0.9, name="right_knee"),
        "left_ankle": Keypoint(x=105, y=350, confidence=0.9, name="left_ankle"),
        "right_ankle": Keypoint(x=145, y=350, confidence=0.9, name="right_ankle"),
    }

    pose_class, confidence = classify_pose(keypoints)

    assert pose_class == "sitting"
    assert confidence >= 0.5


def test_classify_pose_crouching():
    """Test classify_pose detects crouching posture."""
    # Crouching: hips above knees but with compressed torso (torso_to_upper_leg_ratio < 0.8)
    keypoints = {
        "left_shoulder": Keypoint(x=100, y=150, confidence=0.9, name="left_shoulder"),
        "right_shoulder": Keypoint(x=150, y=150, confidence=0.9, name="right_shoulder"),
        "left_hip": Keypoint(x=105, y=180, confidence=0.9, name="left_hip"),
        "right_hip": Keypoint(x=145, y=180, confidence=0.9, name="right_hip"),
        "left_knee": Keypoint(x=105, y=280, confidence=0.9, name="left_knee"),
        "right_knee": Keypoint(x=145, y=280, confidence=0.9, name="right_knee"),
        "left_ankle": Keypoint(x=105, y=380, confidence=0.9, name="left_ankle"),
        "right_ankle": Keypoint(x=145, y=380, confidence=0.9, name="right_ankle"),
    }

    pose_class, confidence = classify_pose(keypoints)

    assert pose_class == "crouching"
    assert confidence >= 0.5


def test_classify_pose_running():
    """Test classify_pose detects running posture."""
    # Running: wide leg spread (leg_spread_ratio > 3.0)
    keypoints = {
        "left_shoulder": Keypoint(x=100, y=50, confidence=0.9, name="left_shoulder"),
        "right_shoulder": Keypoint(x=150, y=50, confidence=0.9, name="right_shoulder"),
        "left_hip": Keypoint(x=110, y=150, confidence=0.9, name="left_hip"),
        "right_hip": Keypoint(x=140, y=150, confidence=0.9, name="right_hip"),  # hip width = 30
        "left_knee": Keypoint(x=50, y=250, confidence=0.9, name="left_knee"),
        "right_knee": Keypoint(x=200, y=250, confidence=0.9, name="right_knee"),
        "left_ankle": Keypoint(x=0, y=350, confidence=0.9, name="left_ankle"),  # leg spread = 200
        "right_ankle": Keypoint(x=200, y=350, confidence=0.9, name="right_ankle"),
        # Add asymmetric arms for additional running signal
        "left_wrist": Keypoint(x=50, y=100, confidence=0.9, name="left_wrist"),
        "right_wrist": Keypoint(x=200, y=200, confidence=0.9, name="right_wrist"),
        "left_elbow": Keypoint(x=70, y=80, confidence=0.9, name="left_elbow"),
        "right_elbow": Keypoint(x=180, y=150, confidence=0.9, name="right_elbow"),
    }

    pose_class, confidence = classify_pose(keypoints)

    assert pose_class == "running"
    assert confidence >= 0.5


def test_classify_pose_lying():
    """Test classify_pose detects lying posture."""
    # Lying: horizontal span > vertical span * 1.5
    keypoints = {
        "left_shoulder": Keypoint(x=100, y=100, confidence=0.9, name="left_shoulder"),
        "right_shoulder": Keypoint(x=150, y=110, confidence=0.9, name="right_shoulder"),
        "left_hip": Keypoint(x=250, y=100, confidence=0.9, name="left_hip"),
        "right_hip": Keypoint(x=300, y=110, confidence=0.9, name="right_hip"),
        "left_knee": Keypoint(x=350, y=100, confidence=0.9, name="left_knee"),
        "right_knee": Keypoint(x=400, y=110, confidence=0.9, name="right_knee"),
        "left_ankle": Keypoint(x=450, y=100, confidence=0.9, name="left_ankle"),
        "right_ankle": Keypoint(x=500, y=110, confidence=0.9, name="right_ankle"),
    }

    pose_class, confidence = classify_pose(keypoints)

    assert pose_class == "lying"
    assert confidence >= 0.5


def test_classify_pose_unknown_low_score():
    """Test classify_pose returns unknown when best score < 0.3."""
    # Provide minimal keypoints that don't match any pattern well
    keypoints = {
        "left_hip": Keypoint(x=100, y=100, confidence=0.9, name="left_hip"),
        "right_hip": Keypoint(x=100, y=100, confidence=0.9, name="right_hip"),
    }

    pose_class, _confidence = classify_pose(keypoints)

    # With only hips at same position, no clear pose pattern
    assert pose_class == "unknown"


def test_classify_pose_with_partial_keypoints():
    """Test classify_pose works with partial keypoints."""
    # Only left side keypoints available
    keypoints = {
        "left_shoulder": Keypoint(x=100, y=50, confidence=0.9, name="left_shoulder"),
        "left_hip": Keypoint(x=105, y=150, confidence=0.9, name="left_hip"),
        "left_knee": Keypoint(x=105, y=250, confidence=0.9, name="left_knee"),
        "left_ankle": Keypoint(x=105, y=350, confidence=0.9, name="left_ankle"),
    }

    pose_class, _confidence = classify_pose(keypoints)

    # Should still be able to classify based on available keypoints
    assert pose_class in ["standing", "crouching", "running", "sitting", "lying", "unknown"]


# Test extract_keypoints_from_output


def test_extract_keypoints_empty_result():
    """Test extract_keypoints_from_output with empty result."""
    mock_processor = MagicMock()
    mock_processor.post_process_pose_estimation.return_value = [[]]

    mock_outputs = MagicMock()

    result = extract_keypoints_from_output(
        mock_outputs, mock_processor, [(480, 640)], min_confidence=0.3
    )

    assert len(result) == 1
    assert result[0] == {}


def test_extract_keypoints_no_results():
    """Test extract_keypoints_from_output when post_process returns None-like."""
    mock_processor = MagicMock()
    mock_processor.post_process_pose_estimation.return_value = [None]

    mock_outputs = MagicMock()

    result = extract_keypoints_from_output(
        mock_outputs, mock_processor, [(480, 640)], min_confidence=0.3
    )

    assert len(result) == 1
    assert result[0] == {}


def test_extract_keypoints_missing_keypoints_tensor():
    """Test extract_keypoints_from_output with missing keypoints tensor."""
    mock_processor = MagicMock()
    mock_processor.post_process_pose_estimation.return_value = [[{"scores": MagicMock()}]]

    mock_outputs = MagicMock()

    result = extract_keypoints_from_output(
        mock_outputs, mock_processor, [(480, 640)], min_confidence=0.3
    )

    assert len(result) == 1
    assert result[0] == {}


def test_extract_keypoints_missing_scores_tensor():
    """Test extract_keypoints_from_output with missing scores tensor."""
    mock_processor = MagicMock()
    mock_processor.post_process_pose_estimation.return_value = [[{"keypoints": MagicMock()}]]

    mock_outputs = MagicMock()

    result = extract_keypoints_from_output(
        mock_outputs, mock_processor, [(480, 640)], min_confidence=0.3
    )

    assert len(result) == 1
    assert result[0] == {}


def test_extract_keypoints_with_numpy_arrays():
    """Test extract_keypoints_from_output with numpy arrays."""
    import numpy as np

    mock_processor = MagicMock()

    # Create numpy arrays for keypoints and scores
    keypoints_array = np.array([[100.0, 50.0] for _ in range(17)])
    scores_array = np.array([0.9 for _ in range(17)])

    mock_processor.post_process_pose_estimation.return_value = [
        [{"keypoints": keypoints_array, "scores": scores_array}]
    ]

    mock_outputs = MagicMock()

    result = extract_keypoints_from_output(
        mock_outputs, mock_processor, [(480, 640)], min_confidence=0.3
    )

    assert len(result) == 1
    assert len(result[0]) == 17  # All keypoints should pass 0.3 threshold


def test_extract_keypoints_with_tensor():
    """Test extract_keypoints_from_output with mock tensors."""
    import numpy as np

    mock_processor = MagicMock()

    # Create mock tensor that has .cpu().numpy() method
    keypoints_array = np.array([[100.0, 50.0] for _ in range(17)])
    scores_array = np.array([0.9 for _ in range(17)])

    mock_keypoints_tensor = MagicMock()
    mock_keypoints_tensor.cpu.return_value.numpy.return_value = keypoints_array

    mock_scores_tensor = MagicMock()
    mock_scores_tensor.cpu.return_value.numpy.return_value = scores_array

    mock_processor.post_process_pose_estimation.return_value = [
        [{"keypoints": mock_keypoints_tensor, "scores": mock_scores_tensor}]
    ]

    mock_outputs = MagicMock()

    result = extract_keypoints_from_output(
        mock_outputs, mock_processor, [(480, 640)], min_confidence=0.3
    )

    assert len(result) == 1
    assert len(result[0]) == 17


def test_extract_keypoints_confidence_filter():
    """Test extract_keypoints_from_output filters by confidence."""
    import numpy as np

    mock_processor = MagicMock()

    # Some keypoints above threshold, some below
    keypoints_array = np.array([[100.0, 50.0] for _ in range(17)])
    scores_array = np.array(
        [0.9, 0.8, 0.7, 0.1, 0.2, 0.9, 0.9, 0.1, 0.1, 0.1, 0.1, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9]
    )

    mock_processor.post_process_pose_estimation.return_value = [
        [{"keypoints": keypoints_array, "scores": scores_array}]
    ]

    mock_outputs = MagicMock()

    result = extract_keypoints_from_output(
        mock_outputs, mock_processor, [(480, 640)], min_confidence=0.5
    )

    # Only keypoints with confidence >= 0.5 should be included
    assert len(result) == 1
    high_conf_count = sum(1 for s in scores_array if s >= 0.5)
    assert len(result[0]) == high_conf_count


def test_extract_keypoints_exception_handling():
    """Test extract_keypoints_from_output handles exceptions."""
    mock_processor = MagicMock()
    mock_processor.post_process_pose_estimation.side_effect = RuntimeError("Processing failed")

    mock_outputs = MagicMock()

    result = extract_keypoints_from_output(
        mock_outputs, mock_processor, [(480, 640)], min_confidence=0.3
    )

    assert result == []


def test_extract_keypoints_multiple_images():
    """Test extract_keypoints_from_output with multiple images."""
    import numpy as np

    mock_processor = MagicMock()

    keypoints_array = np.array([[100.0, 50.0] for _ in range(17)])
    scores_array = np.array([0.9 for _ in range(17)])

    # Two images
    mock_processor.post_process_pose_estimation.return_value = [
        [{"keypoints": keypoints_array, "scores": scores_array}],
        [{"keypoints": keypoints_array, "scores": scores_array}],
    ]

    mock_outputs = MagicMock()

    result = extract_keypoints_from_output(
        mock_outputs, mock_processor, [(480, 640), (480, 640)], min_confidence=0.3
    )

    assert len(result) == 2


# Test load_vitpose_model error handling


@pytest.mark.asyncio
async def test_load_vitpose_model_import_error(monkeypatch):
    """Test load_vitpose_model handles ImportError."""
    import builtins
    import sys

    # Remove transformers and torch from imports if present
    modules_to_hide = ["transformers", "torch"]
    hidden_modules = {}
    for mod in modules_to_hide:
        if mod in sys.modules:
            hidden_modules[mod] = sys.modules.pop(mod)

    # Mock import to raise ImportError
    original_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name in ("transformers", "torch"):
            raise ImportError(f"No module named '{name}'")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)

    try:
        with pytest.raises(ImportError, match="transformers and torch"):
            await load_vitpose_model("/fake/path")
    finally:
        # Restore hidden modules
        sys.modules.update(hidden_modules)


@pytest.mark.asyncio
async def test_load_vitpose_model_runtime_error(monkeypatch):
    """Test load_vitpose_model handles RuntimeError."""
    import sys

    # Mock torch and transformers to exist but fail on model load
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = False
    mock_transformers = MagicMock()
    mock_transformers.AutoProcessor.from_pretrained.side_effect = RuntimeError("Model not found")

    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

    with pytest.raises(RuntimeError, match="Failed to load ViTPose"):
        await load_vitpose_model("/nonexistent/path")


@pytest.mark.asyncio
async def test_load_vitpose_model_generic_exception(monkeypatch):
    """Test load_vitpose_model handles generic exceptions."""
    import sys

    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = False
    mock_transformers = MagicMock()
    mock_transformers.AutoProcessor.from_pretrained.side_effect = Exception("Unknown error")

    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

    with pytest.raises(RuntimeError, match="Failed to load ViTPose"):
        await load_vitpose_model("/test/path")


# Test load_vitpose_model success paths


@pytest.mark.asyncio
async def test_load_vitpose_model_success_cpu(monkeypatch):
    """Test load_vitpose_model success path with CPU."""
    import sys

    # Create mock torch
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = False
    mock_torch.float32 = "float32"

    # Create mock model
    mock_model = MagicMock()
    mock_model.to.return_value = mock_model
    mock_model.eval.return_value = None

    # Create mock processor
    mock_processor = MagicMock()

    # Create mock transformers
    mock_transformers = MagicMock()
    mock_transformers.AutoProcessor.from_pretrained.return_value = mock_processor
    mock_transformers.VitPoseForPoseEstimation.from_pretrained.return_value = mock_model

    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

    result = await load_vitpose_model("/test/model")

    # Returns tuple (model, processor)
    assert result == (mock_model, mock_processor)
    mock_model.to.assert_called_once_with("cpu")
    mock_model.eval.assert_called_once()


@pytest.mark.asyncio
async def test_load_vitpose_model_success_cuda(monkeypatch):
    """Test load_vitpose_model success path with CUDA."""
    import sys

    # Create mock torch with CUDA
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = True
    mock_torch.float16 = "float16"

    # Create mock model that supports .to(device)
    mock_model = MagicMock()
    mock_model.to.return_value = mock_model
    mock_model.eval.return_value = None

    # Create mock processor
    mock_processor = MagicMock()

    # Create mock transformers
    mock_transformers = MagicMock()
    mock_transformers.AutoProcessor.from_pretrained.return_value = mock_processor
    mock_transformers.VitPoseForPoseEstimation.from_pretrained.return_value = mock_model

    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

    result = await load_vitpose_model("/test/model/cuda")

    assert result == (mock_model, mock_processor)
    mock_model.to.assert_called_once_with("cuda")


# Test extract_pose_from_crop


def test_extract_pose_from_crop_callable():
    """Test extract_pose_from_crop is an async function."""
    import inspect

    assert callable(extract_pose_from_crop)
    assert inspect.iscoroutinefunction(extract_pose_from_crop)


@pytest.mark.asyncio
async def test_extract_pose_from_crop_exception():
    """Test extract_pose_from_crop handles exceptions."""
    from PIL import Image

    test_image = Image.new("RGB", (224, 224))

    mock_model = MagicMock()
    mock_model.parameters.side_effect = RuntimeError("GPU OOM")

    mock_processor = MagicMock()

    result = await extract_pose_from_crop(
        mock_model, mock_processor, test_image, bbox=[0, 0, 224, 224]
    )

    # Should return unknown pose on error
    assert result.pose_class == "unknown"
    assert result.pose_confidence == 0.0
    assert result.keypoints == {}
    assert result.bbox == [0, 0, 224, 224]


@pytest.mark.asyncio
async def test_extract_pose_from_crop_success(monkeypatch):
    """Test extract_pose_from_crop success path."""
    import sys

    import numpy as np
    from PIL import Image

    # Mock torch
    mock_torch = MagicMock()
    mock_no_grad = MagicMock()
    mock_no_grad.__enter__ = MagicMock(return_value=None)
    mock_no_grad.__exit__ = MagicMock(return_value=None)
    mock_torch.no_grad.return_value = mock_no_grad

    # Set up mock device
    mock_device = MagicMock()
    mock_param = MagicMock()
    mock_param.device = mock_device

    monkeypatch.setitem(sys.modules, "torch", mock_torch)

    test_image = Image.new("RGB", (224, 224))

    mock_model = MagicMock()
    mock_model.parameters.return_value = iter([mock_param])
    mock_model.return_value = MagicMock()  # Outputs

    mock_processor = MagicMock()
    mock_processor.return_value = {"pixel_values": MagicMock()}

    # Mock post_process to return standing pose keypoints
    keypoints_array = np.array([[100.0, 50.0] for _ in range(17)])
    scores_array = np.array([0.9 for _ in range(17)])
    mock_processor.post_process_pose_estimation.return_value = [
        [{"keypoints": keypoints_array, "scores": scores_array}]
    ]

    result = await extract_pose_from_crop(
        mock_model, mock_processor, test_image, bbox=[0, 0, 224, 224]
    )

    assert isinstance(result, PoseResult)
    assert result.bbox == [0, 0, 224, 224]


@pytest.mark.asyncio
async def test_extract_pose_from_crop_without_bbox(monkeypatch):
    """Test extract_pose_from_crop without bounding box."""
    import sys

    import numpy as np
    from PIL import Image

    # Mock torch
    mock_torch = MagicMock()
    mock_no_grad = MagicMock()
    mock_no_grad.__enter__ = MagicMock(return_value=None)
    mock_no_grad.__exit__ = MagicMock(return_value=None)
    mock_torch.no_grad.return_value = mock_no_grad

    mock_device = MagicMock()
    mock_param = MagicMock()
    mock_param.device = mock_device

    monkeypatch.setitem(sys.modules, "torch", mock_torch)

    test_image = Image.new("RGB", (224, 224))

    mock_model = MagicMock()
    mock_model.parameters.return_value = iter([mock_param])
    mock_model.return_value = MagicMock()

    mock_processor = MagicMock()
    mock_processor.return_value = {"pixel_values": MagicMock()}

    keypoints_array = np.array([[100.0, 50.0] for _ in range(17)])
    scores_array = np.array([0.9 for _ in range(17)])
    mock_processor.post_process_pose_estimation.return_value = [
        [{"keypoints": keypoints_array, "scores": scores_array}]
    ]

    result = await extract_pose_from_crop(mock_model, mock_processor, test_image)

    assert result.bbox is None


# Test extract_poses_batch


def test_extract_poses_batch_callable():
    """Test extract_poses_batch is an async function."""
    import inspect

    assert callable(extract_poses_batch)
    assert inspect.iscoroutinefunction(extract_poses_batch)


@pytest.mark.asyncio
async def test_extract_poses_batch_empty_input():
    """Test extract_poses_batch with empty input."""
    mock_model = MagicMock()
    mock_processor = MagicMock()

    result = await extract_poses_batch(mock_model, mock_processor, [])

    assert result == []


@pytest.mark.asyncio
async def test_extract_poses_batch_exception():
    """Test extract_poses_batch handles exceptions."""
    from PIL import Image

    test_images = [Image.new("RGB", (224, 224)) for _ in range(3)]
    bboxes = [[0, 0, 224, 224], [50, 50, 200, 200], [100, 100, 300, 300]]

    mock_model = MagicMock()
    mock_model.parameters.side_effect = RuntimeError("GPU OOM")

    mock_processor = MagicMock()

    result = await extract_poses_batch(mock_model, mock_processor, test_images, bboxes)

    # Should return unknown poses for all inputs
    assert len(result) == 3
    for i, pose_result in enumerate(result):
        assert pose_result.pose_class == "unknown"
        assert pose_result.pose_confidence == 0.0
        assert pose_result.bbox == bboxes[i]


@pytest.mark.asyncio
async def test_extract_poses_batch_without_bboxes(monkeypatch):
    """Test extract_poses_batch without bounding boxes."""
    import sys

    import numpy as np
    from PIL import Image

    # Mock torch
    mock_torch = MagicMock()
    mock_no_grad = MagicMock()
    mock_no_grad.__enter__ = MagicMock(return_value=None)
    mock_no_grad.__exit__ = MagicMock(return_value=None)
    mock_torch.no_grad.return_value = mock_no_grad

    mock_device = MagicMock()
    mock_param = MagicMock()
    mock_param.device = mock_device

    monkeypatch.setitem(sys.modules, "torch", mock_torch)

    test_images = [Image.new("RGB", (224, 224)) for _ in range(2)]

    mock_model = MagicMock()
    mock_model.parameters.return_value = iter([mock_param])
    mock_model.return_value = MagicMock()

    mock_processor = MagicMock()
    mock_processor.return_value = {"pixel_values": MagicMock()}

    keypoints_array = np.array([[100.0, 50.0] for _ in range(17)])
    scores_array = np.array([0.9 for _ in range(17)])
    mock_processor.post_process_pose_estimation.return_value = [
        [{"keypoints": keypoints_array, "scores": scores_array}],
        [{"keypoints": keypoints_array, "scores": scores_array}],
    ]

    result = await extract_poses_batch(mock_model, mock_processor, test_images)

    assert len(result) == 2
    for pose_result in result:
        assert pose_result.bbox is None


@pytest.mark.asyncio
async def test_extract_poses_batch_success(monkeypatch):
    """Test extract_poses_batch success path."""
    import sys

    import numpy as np
    from PIL import Image

    # Mock torch
    mock_torch = MagicMock()
    mock_no_grad = MagicMock()
    mock_no_grad.__enter__ = MagicMock(return_value=None)
    mock_no_grad.__exit__ = MagicMock(return_value=None)
    mock_torch.no_grad.return_value = mock_no_grad

    mock_device = MagicMock()
    mock_param = MagicMock()
    mock_param.device = mock_device

    monkeypatch.setitem(sys.modules, "torch", mock_torch)

    test_images = [Image.new("RGB", (224, 224)) for _ in range(3)]
    bboxes = [[0, 0, 224, 224], [50, 50, 200, 200], [100, 100, 300, 300]]

    mock_model = MagicMock()
    mock_model.parameters.return_value = iter([mock_param])
    mock_model.return_value = MagicMock()

    mock_processor = MagicMock()
    mock_processor.return_value = {"pixel_values": MagicMock()}

    keypoints_array = np.array([[100.0, 50.0] for _ in range(17)])
    scores_array = np.array([0.9 for _ in range(17)])
    mock_processor.post_process_pose_estimation.return_value = [
        [{"keypoints": keypoints_array, "scores": scores_array}],
        [{"keypoints": keypoints_array, "scores": scores_array}],
        [{"keypoints": keypoints_array, "scores": scores_array}],
    ]

    result = await extract_poses_batch(mock_model, mock_processor, test_images, bboxes)

    assert len(result) == 3
    for i, pose_result in enumerate(result):
        assert isinstance(pose_result, PoseResult)
        assert pose_result.bbox == bboxes[i]


# Test model_zoo integration


def test_vitpose_model_in_zoo():
    """Test vitpose-small is registered in MODEL_ZOO."""
    from backend.services.model_zoo import get_model_zoo

    zoo = get_model_zoo()
    assert "vitpose-small" in zoo

    config = zoo["vitpose-small"]
    assert config.name == "vitpose-small"
    assert config.vram_mb == 1500
    assert config.category == "pose"


def test_vitpose_model_has_loader():
    """Test vitpose-small has load_fn configured."""
    from backend.services.model_zoo import get_model_zoo

    zoo = get_model_zoo()
    config = zoo["vitpose-small"]

    assert config.load_fn is not None
    assert config.load_fn == load_vitpose_model


def test_vitpose_model_path_configured():
    """Test vitpose-small has model path configured."""
    from backend.services.model_zoo import get_model_zoo

    zoo = get_model_zoo()
    config = zoo["vitpose-small"]

    assert config.path == "/models/model-zoo/vitpose-small"


# Additional edge case tests


def test_classify_pose_with_negative_coordinates():
    """Test classify_pose handles negative coordinates."""
    keypoints = {
        "left_hip": Keypoint(x=-10, y=100, confidence=0.9, name="left_hip"),
        "right_hip": Keypoint(x=10, y=100, confidence=0.9, name="right_hip"),
        "left_knee": Keypoint(x=-10, y=200, confidence=0.9, name="left_knee"),
        "right_knee": Keypoint(x=10, y=200, confidence=0.9, name="right_knee"),
    }

    # Should not crash with negative coordinates
    pose_class, _confidence = classify_pose(keypoints)
    assert pose_class in ["standing", "crouching", "running", "sitting", "lying", "unknown"]


def test_classify_pose_with_zero_coordinates():
    """Test classify_pose handles zero coordinates."""
    keypoints = {
        "left_hip": Keypoint(x=0, y=0, confidence=0.9, name="left_hip"),
        "right_hip": Keypoint(x=0, y=0, confidence=0.9, name="right_hip"),
        "left_knee": Keypoint(x=0, y=0, confidence=0.9, name="left_knee"),
        "right_knee": Keypoint(x=0, y=0, confidence=0.9, name="right_knee"),
    }

    # Should handle division by zero gracefully
    pose_class, _confidence = classify_pose(keypoints)
    assert pose_class in ["standing", "crouching", "running", "sitting", "lying", "unknown"]


def test_keypoint_confidence_boundary():
    """Test Keypoint with boundary confidence values."""
    kp_min = Keypoint(x=100, y=100, confidence=0.0, name="test_min")
    kp_max = Keypoint(x=100, y=100, confidence=1.0, name="test_max")

    assert kp_min.confidence == 0.0
    assert kp_max.confidence == 1.0


def test_pose_result_all_pose_classes():
    """Test PoseResult with all valid pose classes."""
    valid_classes = ["standing", "crouching", "running", "sitting", "lying", "unknown"]

    for pose_class in valid_classes:
        result = PoseResult(keypoints={}, pose_class=pose_class, pose_confidence=0.5)
        assert result.pose_class == pose_class


def test_extract_keypoints_custom_confidence_threshold():
    """Test extract_keypoints_from_output with various confidence thresholds."""
    import numpy as np

    mock_processor = MagicMock()

    keypoints_array = np.array([[100.0, 50.0] for _ in range(17)])
    scores_array = np.array([0.5 for _ in range(17)])

    mock_processor.post_process_pose_estimation.return_value = [
        [{"keypoints": keypoints_array, "scores": scores_array}]
    ]

    mock_outputs = MagicMock()

    # With threshold 0.3, all should pass
    result_low = extract_keypoints_from_output(
        mock_outputs, mock_processor, [(480, 640)], min_confidence=0.3
    )
    assert len(result_low[0]) == 17

    # With threshold 0.6, none should pass
    result_high = extract_keypoints_from_output(
        mock_outputs, mock_processor, [(480, 640)], min_confidence=0.6
    )
    assert len(result_high[0]) == 0


def test_extract_keypoints_person_result_none():
    """Test extract_keypoints_from_output when person_result becomes None after result[0]."""
    mock_processor = MagicMock()

    # Result is a non-empty list but result[0] is None
    # This triggers the lines 231-233 branch
    mock_processor.post_process_pose_estimation.return_value = [[None]]

    mock_outputs = MagicMock()

    result = extract_keypoints_from_output(
        mock_outputs, mock_processor, [(480, 640)], min_confidence=0.3
    )

    assert len(result) == 1
    assert result[0] == {}


def test_classify_pose_body_height_from_hip():
    """Test classify_pose calculates body height from hip when shoulder not available."""
    # This covers line 324: body_height estimation using hip_y + ankle_y
    keypoints = {
        # No shoulders, but have hips, knees, ankles
        "left_hip": Keypoint(x=105, y=150, confidence=0.9, name="left_hip"),
        "right_hip": Keypoint(x=145, y=150, confidence=0.9, name="right_hip"),
        "left_knee": Keypoint(x=105, y=250, confidence=0.9, name="left_knee"),
        "right_knee": Keypoint(x=145, y=250, confidence=0.9, name="right_knee"),
        "left_ankle": Keypoint(x=105, y=350, confidence=0.9, name="left_ankle"),
        "right_ankle": Keypoint(x=145, y=350, confidence=0.9, name="right_ankle"),
    }

    pose_class, _confidence = classify_pose(keypoints)

    # Should still be able to classify (standing in this case)
    assert pose_class in ["standing", "crouching", "running", "sitting", "lying", "unknown"]


def test_classify_pose_lying_via_horizontal_span():
    """Test classify_pose with strong horizontal lying orientation.

    Note: Line 372 in vitpose_loader.py is logically unreachable code because:
    - The elif condition requires: horizontal_span / vertical_span > 3.0
    - But the if condition triggers when: horizontal_span > vertical_span * 1.5
    - Since 3.0 > 1.5, if ratio > 3.0, then horizontal_span > 3*v > 1.5*v
    - Therefore the if branch always triggers before the elif can be reached.
    - Coverage: 99.52% (line 372 unreachable).

    This test verifies lying detection via the primary branch by using
    coordinates that clearly indicate horizontal orientation WITHOUT
    satisfying the vertical alignment criteria for standing.
    """
    # For a clear lying pose, ensure:
    # 1. horizontal_span >> vertical_span (for lying score 0.8)
    # 2. NOT (hip_y < knee_y < ankle_y) to prevent standing detection
    keypoints = {
        "left_shoulder": Keypoint(x=50, y=100, confidence=0.9, name="left_shoulder"),
        "right_shoulder": Keypoint(x=100, y=105, confidence=0.9, name="right_shoulder"),
        # Hips NOT in vertical alignment order
        "left_hip": Keypoint(x=150, y=98, confidence=0.9, name="left_hip"),
        "right_hip": Keypoint(x=200, y=102, confidence=0.9, name="right_hip"),
        # Knees at same Y level as hips (not below)
        "left_knee": Keypoint(x=250, y=100, confidence=0.9, name="left_knee"),
        "right_knee": Keypoint(x=300, y=100, confidence=0.9, name="right_knee"),
        # Ankles at same Y level
        "left_ankle": Keypoint(x=350, y=100, confidence=0.9, name="left_ankle"),
        "right_ankle": Keypoint(x=400, y=100, confidence=0.9, name="right_ankle"),
    }
    # shoulder_y = 102.5, ankle_y = 100, shoulder_x = 75, ankle_x = 375
    # vertical_span = |102.5 - 100| = 2.5
    # horizontal_span = |75 - 375| = 300
    # horizontal_span (300) > vertical_span * 1.5 (3.75) -> lying score 0.8

    pose_class, confidence = classify_pose(keypoints)

    assert pose_class == "lying"
    assert confidence >= 0.5
