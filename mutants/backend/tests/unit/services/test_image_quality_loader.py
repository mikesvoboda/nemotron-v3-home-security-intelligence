"""Unit tests for image_quality_loader service.

Tests for the BRISQUE image quality assessment model loader and quality functions.
"""

from unittest.mock import MagicMock

import pytest

from backend.services.image_quality_loader import (
    BRISQUE_BLUR_THRESHOLD,
    BRISQUE_LOW_QUALITY_THRESHOLD,
    BRISQUE_NOISE_THRESHOLD,
    ImageQualityResult,
    assess_image_quality,
    detect_quality_change,
    interpret_blur_with_motion,
    load_brisque_model,
)

# =============================================================================
# Test ImageQualityResult dataclass
# =============================================================================


def test_image_quality_result_creation():
    """Test ImageQualityResult dataclass creation."""
    result = ImageQualityResult(
        quality_score=75.0,
        brisque_score=25.0,
        is_blurry=False,
        is_noisy=False,
        is_low_quality=False,
        quality_issues=[],
    )

    assert result.quality_score == 75.0
    assert result.brisque_score == 25.0
    assert result.is_blurry is False
    assert result.is_noisy is False
    assert result.is_low_quality is False
    assert result.quality_issues == []


def test_image_quality_result_with_issues():
    """Test ImageQualityResult with quality issues."""
    result = ImageQualityResult(
        quality_score=40.0,
        brisque_score=60.0,
        is_blurry=True,
        is_noisy=True,
        is_low_quality=True,
        quality_issues=["blur detected", "noise/artifacts detected"],
    )

    assert result.is_blurry is True
    assert result.is_noisy is True
    assert result.is_low_quality is True
    assert len(result.quality_issues) == 2


def test_image_quality_result_to_dict():
    """Test ImageQualityResult.to_dict() method."""
    result = ImageQualityResult(
        quality_score=80.0,
        brisque_score=20.0,
        is_blurry=False,
        is_noisy=False,
        is_low_quality=False,
        quality_issues=[],
    )

    d = result.to_dict()

    assert d["quality_score"] == 80.0
    assert d["brisque_score"] == 20.0
    assert d["is_blurry"] is False
    assert d["is_noisy"] is False
    assert d["is_low_quality"] is False
    assert d["quality_issues"] == []


def test_image_quality_result_is_good_quality():
    """Test ImageQualityResult.is_good_quality property."""
    # Good quality - no issues
    good_result = ImageQualityResult(
        quality_score=85.0,
        brisque_score=15.0,
        is_blurry=False,
        is_noisy=False,
        is_low_quality=False,
    )
    assert good_result.is_good_quality is True

    # Bad quality - blurry
    blurry_result = ImageQualityResult(
        quality_score=45.0,
        brisque_score=55.0,
        is_blurry=True,
        is_noisy=False,
        is_low_quality=True,
    )
    assert blurry_result.is_good_quality is False

    # Bad quality - noisy
    noisy_result = ImageQualityResult(
        quality_score=35.0,
        brisque_score=65.0,
        is_blurry=False,
        is_noisy=True,
        is_low_quality=True,
    )
    assert noisy_result.is_good_quality is False


def test_image_quality_result_format_context_good():
    """Test ImageQualityResult.format_context() for good quality."""
    result = ImageQualityResult(
        quality_score=90.0,
        brisque_score=10.0,
        is_blurry=False,
        is_noisy=False,
        is_low_quality=False,
    )

    context = result.format_context()

    assert "Good image quality" in context
    assert "90" in context
    assert "/100" in context


def test_image_quality_result_format_context_issues():
    """Test ImageQualityResult.format_context() with issues."""
    result = ImageQualityResult(
        quality_score=40.0,
        brisque_score=60.0,
        is_blurry=True,
        is_noisy=False,
        is_low_quality=True,
        quality_issues=["blur detected"],
    )

    context = result.format_context()

    assert "Image quality issues detected" in context
    assert "blur detected" in context
    assert "40" in context


def test_image_quality_result_format_context_general_degradation():
    """Test ImageQualityResult.format_context() with no specific issues."""
    result = ImageQualityResult(
        quality_score=50.0,
        brisque_score=50.0,
        is_blurry=False,
        is_noisy=False,
        is_low_quality=True,
        quality_issues=[],  # Empty but low quality
    )

    context = result.format_context()

    assert "general degradation" in context


def test_image_quality_result_default_issues():
    """Test ImageQualityResult default quality_issues."""
    result = ImageQualityResult(
        quality_score=70.0,
        brisque_score=30.0,
        is_blurry=False,
        is_noisy=False,
        is_low_quality=False,
    )

    assert result.quality_issues == []


# =============================================================================
# Test constants
# =============================================================================


def test_brisque_thresholds_defined():
    """Test BRISQUE thresholds are defined."""
    assert BRISQUE_BLUR_THRESHOLD == 50.0
    assert BRISQUE_NOISE_THRESHOLD == 60.0
    assert BRISQUE_LOW_QUALITY_THRESHOLD == 40.0


def test_brisque_thresholds_hierarchy():
    """Test BRISQUE thresholds are in expected order."""
    # Low quality threshold should be lowest (most sensitive)
    # Noise threshold should be highest (least sensitive)
    assert BRISQUE_LOW_QUALITY_THRESHOLD < BRISQUE_BLUR_THRESHOLD
    assert BRISQUE_BLUR_THRESHOLD < BRISQUE_NOISE_THRESHOLD


# =============================================================================
# Test detect_quality_change
# =============================================================================


def test_detect_quality_change_no_previous():
    """Test detect_quality_change with no previous frame."""
    current = ImageQualityResult(
        quality_score=80.0,
        brisque_score=20.0,
        is_blurry=False,
        is_noisy=False,
        is_low_quality=False,
    )

    detected, description = detect_quality_change(current, None)

    assert detected is False
    assert "First frame" in description


def test_detect_quality_change_stable():
    """Test detect_quality_change with stable quality."""
    previous = ImageQualityResult(
        quality_score=80.0,
        brisque_score=20.0,
        is_blurry=False,
        is_noisy=False,
        is_low_quality=False,
    )
    current = ImageQualityResult(
        quality_score=78.0,
        brisque_score=22.0,
        is_blurry=False,
        is_noisy=False,
        is_low_quality=False,
    )

    detected, description = detect_quality_change(current, previous)

    assert detected is False
    assert "stable" in description.lower()


def test_detect_quality_change_significant_drop():
    """Test detect_quality_change with significant quality drop."""
    previous = ImageQualityResult(
        quality_score=85.0,
        brisque_score=15.0,
        is_blurry=False,
        is_noisy=False,
        is_low_quality=False,
    )
    current = ImageQualityResult(
        quality_score=40.0,
        brisque_score=60.0,
        is_blurry=True,
        is_noisy=False,
        is_low_quality=True,
    )

    detected, description = detect_quality_change(current, previous)

    assert detected is True
    assert "Sudden quality drop" in description
    assert "85" in description
    assert "40" in description
    assert "obstruction" in description.lower() or "tampering" in description.lower()


def test_detect_quality_change_custom_threshold():
    """Test detect_quality_change with custom threshold."""
    previous = ImageQualityResult(
        quality_score=80.0,
        brisque_score=20.0,
        is_blurry=False,
        is_noisy=False,
        is_low_quality=False,
    )
    current = ImageQualityResult(
        quality_score=70.0,
        brisque_score=30.0,
        is_blurry=False,
        is_noisy=False,
        is_low_quality=False,
    )

    # Default threshold is 30, drop of 10 should not trigger
    detected_default, _ = detect_quality_change(current, previous)
    assert detected_default is False

    # With threshold of 5, drop of 10 should trigger
    detected_custom, description = detect_quality_change(current, previous, drop_threshold=5.0)
    assert detected_custom is True
    assert "Sudden quality drop" in description


def test_detect_quality_change_quality_improvement():
    """Test detect_quality_change ignores quality improvements."""
    previous = ImageQualityResult(
        quality_score=50.0,
        brisque_score=50.0,
        is_blurry=True,
        is_noisy=False,
        is_low_quality=True,
    )
    current = ImageQualityResult(
        quality_score=90.0,  # Improvement
        brisque_score=10.0,
        is_blurry=False,
        is_noisy=False,
        is_low_quality=False,
    )

    detected, _description = detect_quality_change(current, previous)

    # Improvement should not trigger alert
    assert detected is False


# =============================================================================
# Test interpret_blur_with_motion
# =============================================================================


def test_interpret_blur_with_motion_no_blur():
    """Test interpret_blur_with_motion with no blur."""
    result = ImageQualityResult(
        quality_score=85.0,
        brisque_score=15.0,
        is_blurry=False,
        is_noisy=False,
        is_low_quality=False,
    )

    interpretation = interpret_blur_with_motion(result, has_person=True)

    assert "Clear image" in interpretation
    assert "no motion blur" in interpretation


def test_interpret_blur_with_motion_blur_with_fast_person():
    """Test interpret_blur_with_motion with blur and fast-moving person."""
    result = ImageQualityResult(
        quality_score=40.0,
        brisque_score=60.0,
        is_blurry=True,
        is_noisy=False,
        is_low_quality=True,
    )

    interpretation = interpret_blur_with_motion(
        result, has_person=True, person_speed_estimate="fast"
    )

    assert "motion blur" in interpretation.lower()
    assert "fast" in interpretation.lower()
    assert "running" in interpretation.lower()


def test_interpret_blur_with_motion_blur_with_person():
    """Test interpret_blur_with_motion with blur and person (unknown speed)."""
    result = ImageQualityResult(
        quality_score=45.0,
        brisque_score=55.0,
        is_blurry=True,
        is_noisy=False,
        is_low_quality=True,
    )

    interpretation = interpret_blur_with_motion(result, has_person=True)

    assert "Motion blur" in interpretation
    assert "person" in interpretation.lower()
    assert "movement" in interpretation.lower()


def test_interpret_blur_with_motion_blur_no_person():
    """Test interpret_blur_with_motion with blur but no person."""
    result = ImageQualityResult(
        quality_score=45.0,
        brisque_score=55.0,
        is_blurry=True,
        is_noisy=False,
        is_low_quality=True,
    )

    interpretation = interpret_blur_with_motion(result, has_person=False)

    assert "blur" in interpretation.lower()
    assert "camera issue" in interpretation.lower() or "obstruction" in interpretation.lower()


def test_interpret_blur_with_motion_blur_slow_person():
    """Test interpret_blur_with_motion with blur and slow-moving person."""
    result = ImageQualityResult(
        quality_score=48.0,
        brisque_score=52.0,
        is_blurry=True,
        is_noisy=False,
        is_low_quality=True,
    )

    interpretation = interpret_blur_with_motion(
        result, has_person=True, person_speed_estimate="slow"
    )

    # Slow speed should use the default person blur message (not fast)
    # The generic message mentions "running or quick movements" as a possibility
    assert "Motion blur" in interpretation
    # It should NOT say "indicates fast movement" which is the fast-specific message
    assert "indicates fast movement" not in interpretation.lower()


# =============================================================================
# Test load_brisque_model error handling
# =============================================================================


@pytest.mark.asyncio
async def test_load_brisque_model_import_error(monkeypatch):
    """Test load_brisque_model handles ImportError."""
    import builtins
    import sys

    # Remove pyiqa from imports if present
    modules_to_hide = ["pyiqa"]
    hidden_modules = {}
    for mod in modules_to_hide:
        for key in list(sys.modules.keys()):
            if key == mod or key.startswith(f"{mod}."):
                hidden_modules[key] = sys.modules.pop(key)

    # Mock import to raise ImportError
    original_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "pyiqa" or name.startswith("pyiqa."):
            raise ImportError(f"No module named '{name}'")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)

    try:
        with pytest.raises(ImportError, match="pyiqa"):
            await load_brisque_model("")
    finally:
        sys.modules.update(hidden_modules)


@pytest.mark.asyncio
async def test_load_brisque_model_runtime_error(monkeypatch):
    """Test load_brisque_model handles RuntimeError."""
    import sys

    mock_pyiqa = MagicMock()
    mock_pyiqa.create_metric.side_effect = RuntimeError("Failed to initialize metric")

    monkeypatch.setitem(sys.modules, "pyiqa", mock_pyiqa)

    with pytest.raises(RuntimeError, match="Failed to load BRISQUE metric"):
        await load_brisque_model("")


# =============================================================================
# Test load_brisque_model success path
# =============================================================================


@pytest.mark.asyncio
async def test_load_brisque_model_success(monkeypatch):
    """Test load_brisque_model success path."""
    import sys

    mock_metric = MagicMock()

    mock_pyiqa = MagicMock()
    mock_pyiqa.create_metric.return_value = mock_metric

    monkeypatch.setitem(sys.modules, "pyiqa", mock_pyiqa)

    result = await load_brisque_model("")

    assert "metric" in result
    assert result["metric"] is mock_metric
    mock_pyiqa.create_metric.assert_called_once_with("brisque", device="cpu")


@pytest.mark.asyncio
async def test_load_brisque_model_ignores_path(monkeypatch):
    """Test load_brisque_model ignores the model_path argument."""
    import sys

    mock_metric = MagicMock()

    mock_pyiqa = MagicMock()
    mock_pyiqa.create_metric.return_value = mock_metric

    monkeypatch.setitem(sys.modules, "pyiqa", mock_pyiqa)

    # Path is ignored since pyiqa uses built-in metric
    result = await load_brisque_model("/some/random/path")

    assert "metric" in result
    # Should still create brisque metric regardless of path
    mock_pyiqa.create_metric.assert_called_once_with("brisque", device="cpu")


# =============================================================================
# Test assess_image_quality
# =============================================================================


def test_assess_image_quality_is_async():
    """Test assess_image_quality is an async function."""
    import inspect

    assert callable(assess_image_quality)
    assert inspect.iscoroutinefunction(assess_image_quality)


def test_assess_image_quality_signature():
    """Test assess_image_quality function signature."""
    import inspect

    sig = inspect.signature(assess_image_quality)
    params = list(sig.parameters.keys())

    assert "model_data" in params
    assert "image" in params
    assert "blur_threshold" in params
    assert "noise_threshold" in params
    assert "low_quality_threshold" in params

    # Check default values
    assert sig.parameters["blur_threshold"].default == BRISQUE_BLUR_THRESHOLD
    assert sig.parameters["noise_threshold"].default == BRISQUE_NOISE_THRESHOLD
    assert sig.parameters["low_quality_threshold"].default == BRISQUE_LOW_QUALITY_THRESHOLD


@pytest.mark.asyncio
async def test_assess_image_quality_import_error(monkeypatch):
    """Test assess_image_quality handles import error."""
    import builtins
    import sys

    from PIL import Image

    test_image = Image.new("RGB", (100, 100))
    model_data = {"metric": MagicMock()}

    # Remove torch and torchvision
    modules_to_hide = ["torch", "torchvision"]
    hidden_modules = {}
    for mod in modules_to_hide:
        for key in list(sys.modules.keys()):
            if key == mod or key.startswith(f"{mod}."):
                hidden_modules[key] = sys.modules.pop(key)

    original_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name in ("torch", "torchvision") or name.startswith(("torch.", "torchvision.")):
            raise ImportError(f"No module named '{name}'")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)

    try:
        with pytest.raises(RuntimeError, match="torch and torchvision required"):
            await assess_image_quality(model_data, test_image)
    finally:
        sys.modules.update(hidden_modules)


@pytest.mark.asyncio
async def test_assess_image_quality_success(monkeypatch):
    """Test assess_image_quality success path."""
    import sys

    from PIL import Image

    # Create test image
    test_image = Image.new("RGB", (100, 100))

    # Create mock torch
    mock_torch = MagicMock()
    mock_tensor = MagicMock()
    mock_tensor.unsqueeze.return_value = mock_tensor

    mock_no_grad = MagicMock()
    mock_no_grad.__enter__ = MagicMock(return_value=None)
    mock_no_grad.__exit__ = MagicMock(return_value=None)
    mock_torch.no_grad.return_value = mock_no_grad

    # Mock torchvision transforms
    mock_transforms = MagicMock()
    mock_compose = MagicMock()
    mock_compose.return_value = mock_tensor
    mock_transforms.Compose.return_value = mock_compose
    mock_transforms.ToTensor.return_value = MagicMock()

    mock_torchvision = MagicMock()
    mock_torchvision.transforms = mock_transforms

    # Create mock metric that returns a good score
    mock_metric = MagicMock()
    mock_score_tensor = MagicMock()
    mock_score_tensor.item.return_value = 25.0  # Good quality (low BRISQUE score)
    mock_metric.return_value = mock_score_tensor

    model_data = {"metric": mock_metric}

    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    monkeypatch.setitem(sys.modules, "torchvision", mock_torchvision)
    monkeypatch.setitem(sys.modules, "torchvision.transforms", mock_transforms)

    result = await assess_image_quality(model_data, test_image)

    assert isinstance(result, ImageQualityResult)
    assert result.quality_score == 75.0  # 100 - 25
    assert result.brisque_score == 25.0
    assert result.is_good_quality is True


# =============================================================================
# Test function signatures and types
# =============================================================================


def test_load_brisque_model_is_async():
    """Test load_brisque_model is an async function."""
    import inspect

    assert callable(load_brisque_model)
    assert inspect.iscoroutinefunction(load_brisque_model)


def test_load_brisque_model_signature():
    """Test load_brisque_model function signature."""
    import inspect

    sig = inspect.signature(load_brisque_model)
    params = list(sig.parameters.keys())
    assert "model_path" in params


def test_detect_quality_change_signature():
    """Test detect_quality_change function signature."""
    import inspect

    sig = inspect.signature(detect_quality_change)
    params = list(sig.parameters.keys())

    assert "current_quality" in params
    assert "previous_quality" in params
    assert "drop_threshold" in params
    assert sig.parameters["drop_threshold"].default == 30.0


def test_interpret_blur_with_motion_signature():
    """Test interpret_blur_with_motion function signature."""
    import inspect

    sig = inspect.signature(interpret_blur_with_motion)
    params = list(sig.parameters.keys())

    assert "quality_result" in params
    assert "has_person" in params
    assert "person_speed_estimate" in params
    assert sig.parameters["person_speed_estimate"].default is None


# =============================================================================
# Test model_zoo integration
# =============================================================================


def test_brisque_in_model_zoo():
    """Test brisque is registered in MODEL_ZOO."""
    from backend.services.model_zoo import get_model_zoo

    zoo = get_model_zoo()
    assert "brisque-quality" in zoo

    config = zoo["brisque-quality"]
    assert config.name == "brisque-quality"
    assert config.category == "quality-assessment"
    # BRISQUE is currently disabled in model_zoo
    assert config.enabled is False
    # BRISQUE is CPU-based, should have 0 VRAM
    assert config.vram_mb == 0


def test_brisque_model_config_load_fn():
    """Test brisque model config has correct load function."""
    from backend.services.model_zoo import get_model_zoo

    zoo = get_model_zoo()
    config = zoo["brisque-quality"]
    assert config.load_fn is load_brisque_model


# =============================================================================
# Test edge cases
# =============================================================================


def test_image_quality_result_boundary_scores():
    """Test ImageQualityResult with boundary scores."""
    # Minimum score
    min_result = ImageQualityResult(
        quality_score=0.0,
        brisque_score=100.0,
        is_blurry=True,
        is_noisy=True,
        is_low_quality=True,
    )
    assert min_result.is_good_quality is False

    # Maximum score
    max_result = ImageQualityResult(
        quality_score=100.0,
        brisque_score=0.0,
        is_blurry=False,
        is_noisy=False,
        is_low_quality=False,
    )
    assert max_result.is_good_quality is True


def test_detect_quality_change_exact_threshold():
    """Test detect_quality_change at exact threshold boundary."""
    previous = ImageQualityResult(
        quality_score=80.0,
        brisque_score=20.0,
        is_blurry=False,
        is_noisy=False,
        is_low_quality=False,
    )
    current = ImageQualityResult(
        quality_score=50.0,  # Exactly 30 drop
        brisque_score=50.0,
        is_blurry=True,
        is_noisy=False,
        is_low_quality=True,
    )

    detected, _ = detect_quality_change(current, previous, drop_threshold=30.0)
    assert detected is True


def test_image_quality_result_to_dict_keys():
    """Test ImageQualityResult.to_dict() contains all expected keys."""
    result = ImageQualityResult(
        quality_score=70.0,
        brisque_score=30.0,
        is_blurry=False,
        is_noisy=False,
        is_low_quality=False,
        quality_issues=["test"],
    )

    d = result.to_dict()

    expected_keys = {
        "quality_score",
        "brisque_score",
        "is_blurry",
        "is_noisy",
        "is_low_quality",
        "quality_issues",
    }
    assert set(d.keys()) == expected_keys
