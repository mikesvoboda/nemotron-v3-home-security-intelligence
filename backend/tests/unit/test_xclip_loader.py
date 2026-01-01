"""Unit tests for xclip_loader service.

Tests for the X-CLIP model loader and action classifier.
"""

from unittest.mock import MagicMock

import pytest

from backend.services.xclip_loader import (
    SECURITY_ACTION_PROMPTS,
    classify_actions,
    get_action_risk_weight,
    is_suspicious_action,
    load_xclip_model,
    sample_frames_from_batch,
)

# Test constants


def test_security_action_prompts_not_empty():
    """Test that security action prompts are defined."""
    assert len(SECURITY_ACTION_PROMPTS) > 0


def test_security_action_prompts_are_strings():
    """Test that all prompts are strings."""
    assert all(isinstance(p, str) for p in SECURITY_ACTION_PROMPTS)


def test_security_prompts_have_suspicious_actions():
    """Test that prompts include suspicious actions."""
    prompts_lower = [p.lower() for p in SECURITY_ACTION_PROMPTS]
    assert any("loitering" in p for p in prompts_lower)
    assert any("suspiciously" in p for p in prompts_lower)
    assert any("breaking" in p for p in prompts_lower)


def test_security_prompts_have_normal_actions():
    """Test that prompts include normal actions."""
    prompts_lower = [p.lower() for p in SECURITY_ACTION_PROMPTS]
    assert any("walking normally" in p for p in prompts_lower)
    assert any("delivering" in p for p in prompts_lower)


# Test sample_frames_from_batch


def test_sample_frames_exact_count():
    """Test sampling when input equals target count."""
    frames = [f"frame_{i}.jpg" for i in range(8)]
    result = sample_frames_from_batch(frames, target_count=8)
    assert result == frames


def test_sample_frames_fewer_than_target():
    """Test sampling when fewer frames than target."""
    frames = [f"frame_{i}.jpg" for i in range(5)]
    result = sample_frames_from_batch(frames, target_count=8)
    assert result == frames  # Returns all frames unchanged


def test_sample_frames_more_than_target():
    """Test sampling when more frames than target."""
    frames = [f"frame_{i}.jpg" for i in range(16)]
    result = sample_frames_from_batch(frames, target_count=8)
    assert len(result) == 8
    # Should be uniformly sampled
    assert result[0] == "frame_0.jpg"


def test_sample_frames_custom_target():
    """Test sampling with custom target count."""
    frames = [f"frame_{i}.jpg" for i in range(20)]
    result = sample_frames_from_batch(frames, target_count=4)
    assert len(result) == 4


def test_sample_frames_single_frame():
    """Test sampling with single frame."""
    frames = ["frame_0.jpg"]
    result = sample_frames_from_batch(frames, target_count=8)
    assert result == frames


def test_sample_frames_empty():
    """Test sampling with empty list."""
    result = sample_frames_from_batch([], target_count=8)
    assert result == []


# Test is_suspicious_action


def test_is_suspicious_loitering():
    """Test loitering is detected as suspicious."""
    assert is_suspicious_action("a person loitering") is True


def test_is_suspicious_looking_suspiciously():
    """Test suspiciously looking is detected."""
    assert is_suspicious_action("a person looking around suspiciously") is True


def test_is_suspicious_running_away():
    """Test running away is detected as suspicious."""
    assert is_suspicious_action("a person running away") is True


def test_is_suspicious_trying_door():
    """Test trying door handle is detected."""
    assert is_suspicious_action("a person trying a door handle") is True


def test_is_suspicious_hiding():
    """Test hiding is detected as suspicious."""
    assert is_suspicious_action("a person hiding near bushes") is True


def test_is_suspicious_vandalizing():
    """Test vandalizing is detected as suspicious."""
    assert is_suspicious_action("a person vandalizing property") is True


def test_is_suspicious_breaking():
    """Test breaking in is detected as suspicious."""
    assert is_suspicious_action("a person breaking in") is True


def test_is_suspicious_checking_windows():
    """Test checking windows is detected as suspicious."""
    assert is_suspicious_action("a person checking windows") is True


def test_is_suspicious_taking_photos():
    """Test taking photos is detected as suspicious."""
    assert is_suspicious_action("a person taking photos of house") is True


def test_not_suspicious_walking():
    """Test walking normally is not suspicious."""
    assert is_suspicious_action("a person walking normally") is False


def test_not_suspicious_delivering():
    """Test delivering package is not suspicious."""
    assert is_suspicious_action("a person delivering a package") is False


def test_not_suspicious_knocking():
    """Test knocking on door is not suspicious."""
    assert is_suspicious_action("a person knocking on door") is False


def test_not_suspicious_ringing():
    """Test ringing doorbell is not suspicious."""
    assert is_suspicious_action("a person ringing doorbell") is False


def test_is_suspicious_case_insensitive():
    """Test suspicious check is case insensitive."""
    assert is_suspicious_action("A PERSON LOITERING") is True


# Test get_action_risk_weight


def test_risk_weight_breaking_in():
    """Test high risk weight for breaking in."""
    weight = get_action_risk_weight("a person breaking in")
    assert weight == 1.0


def test_risk_weight_vandalizing():
    """Test high risk weight for vandalizing."""
    weight = get_action_risk_weight("a person vandalizing property")
    assert weight == 1.0


def test_risk_weight_hiding():
    """Test high risk weight for hiding."""
    weight = get_action_risk_weight("a person hiding near bushes")
    assert weight == 1.0


def test_risk_weight_trying_door():
    """Test high risk weight for trying door handle."""
    weight = get_action_risk_weight("a person trying door handle")
    assert weight == 1.0


def test_risk_weight_loitering():
    """Test medium risk weight for loitering."""
    weight = get_action_risk_weight("a person loitering")
    assert weight == 0.7


def test_risk_weight_suspiciously():
    """Test medium risk weight for suspicious behavior."""
    weight = get_action_risk_weight("a person looking around suspiciously")
    assert weight == 0.7


def test_risk_weight_running_away():
    """Test medium risk weight for running away."""
    weight = get_action_risk_weight("a person running away")
    assert weight == 0.7


def test_risk_weight_taking_photos():
    """Test medium risk weight for taking photos."""
    weight = get_action_risk_weight("a person taking photos")
    assert weight == 0.7


def test_risk_weight_delivering():
    """Test low risk weight for delivering."""
    weight = get_action_risk_weight("a person delivering a package")
    assert weight == 0.2


def test_risk_weight_knocking():
    """Test low risk weight for knocking."""
    weight = get_action_risk_weight("a person knocking on door")
    assert weight == 0.2


def test_risk_weight_ringing():
    """Test low risk weight for ringing doorbell."""
    weight = get_action_risk_weight("a person ringing doorbell")
    assert weight == 0.2


def test_risk_weight_walking_normally():
    """Test low risk weight for walking normally."""
    weight = get_action_risk_weight("a person walking normally")
    assert weight == 0.2


def test_risk_weight_leaving_package():
    """Test low risk weight for leaving package."""
    weight = get_action_risk_weight("a person leaving package at door")
    assert weight == 0.2


def test_risk_weight_unknown_action():
    """Test neutral risk weight for unknown actions."""
    weight = get_action_risk_weight("a person doing something")
    assert weight == 0.5


def test_risk_weight_case_insensitive():
    """Test risk weight is case insensitive."""
    weight = get_action_risk_weight("A PERSON BREAKING IN")
    assert weight == 1.0


# Test load_xclip_model error handling


@pytest.mark.asyncio
async def test_load_xclip_model_import_error(monkeypatch):
    """Test load_xclip_model handles ImportError."""
    import builtins
    import sys

    # Remove transformers from imports if present
    modules_to_hide = ["transformers"]
    hidden_modules = {}
    for mod in modules_to_hide:
        if mod in sys.modules:
            hidden_modules[mod] = sys.modules.pop(mod)

    # Mock import to raise ImportError
    original_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "transformers":
            raise ImportError("No module named 'transformers'")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)

    try:
        with pytest.raises(ImportError, match="transformers"):
            await load_xclip_model("/fake/path")
    finally:
        # Restore hidden modules
        sys.modules.update(hidden_modules)


@pytest.mark.asyncio
async def test_load_xclip_model_runtime_error(monkeypatch):
    """Test load_xclip_model handles RuntimeError."""
    import sys

    # Mock transformers to exist but fail on model load
    mock_transformers = MagicMock()
    mock_transformers.XCLIPProcessor.from_pretrained.side_effect = RuntimeError("Model not found")

    monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

    with pytest.raises(RuntimeError, match="Failed to load X-CLIP"):
        await load_xclip_model("/nonexistent/path")


# Test classify_actions


@pytest.mark.asyncio
async def test_classify_actions_empty_frames():
    """Test classify_actions raises error on empty frames."""
    model_dict = {"model": MagicMock(), "processor": MagicMock()}

    with pytest.raises(ValueError, match="At least one frame"):
        await classify_actions(model_dict, frames=[])


# Test load_xclip_model success path


@pytest.mark.asyncio
async def test_load_xclip_model_success_cpu(monkeypatch):
    """Test load_xclip_model success path with CPU."""
    import sys

    # Create mock torch
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = False

    # Create mock model
    mock_model = MagicMock()
    mock_model.eval.return_value = None

    # Create mock processor
    mock_processor = MagicMock()

    # Create mock transformers
    mock_transformers = MagicMock()
    mock_transformers.XCLIPProcessor.from_pretrained.return_value = mock_processor
    mock_transformers.XCLIPModel.from_pretrained.return_value = mock_model

    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

    result = await load_xclip_model("/test/model")

    assert "model" in result
    assert "processor" in result
    mock_model.eval.assert_called_once()


@pytest.mark.asyncio
async def test_load_xclip_model_success_cuda(monkeypatch):
    """Test load_xclip_model success path with CUDA."""
    import sys

    # Create mock torch with CUDA
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = True

    # Create mock model that supports cuda().half()
    mock_cuda_model = MagicMock()
    mock_half_model = MagicMock()
    mock_cuda_model.half.return_value = mock_half_model
    mock_half_model.eval.return_value = None

    mock_model = MagicMock()
    mock_model.cuda.return_value = mock_cuda_model

    # Create mock processor
    mock_processor = MagicMock()

    # Create mock transformers
    mock_transformers = MagicMock()
    mock_transformers.XCLIPProcessor.from_pretrained.return_value = mock_processor
    mock_transformers.XCLIPModel.from_pretrained.return_value = mock_model

    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

    result = await load_xclip_model("/test/model/cuda")

    assert "model" in result
    assert "processor" in result
    mock_model.cuda.assert_called_once()


# Test classify_actions callable


def test_classify_actions_callable():
    """Test classify_actions is an async function."""
    import inspect

    assert callable(classify_actions)
    assert inspect.iscoroutinefunction(classify_actions)


# Test classify_actions with custom prompts


def test_classify_actions_accepts_prompts_parameter():
    """Test classify_actions has prompts parameter."""
    import inspect

    sig = inspect.signature(classify_actions)
    assert "prompts" in sig.parameters
    assert sig.parameters["prompts"].default is None


def test_classify_actions_accepts_frames_parameter():
    """Test classify_actions has frames parameter."""
    import inspect

    sig = inspect.signature(classify_actions)
    assert "frames" in sig.parameters


@pytest.mark.asyncio
async def test_classify_actions_runtime_error():
    """Test classify_actions handles runtime errors."""
    from PIL import Image

    test_frames = [Image.new("RGB", (224, 224)) for _ in range(4)]

    # Create model dict with model that raises error
    mock_model = MagicMock()
    mock_model.parameters.side_effect = RuntimeError("GPU OOM")

    model_dict = {"model": mock_model, "processor": MagicMock()}

    with pytest.raises(RuntimeError, match="X-CLIP classification failed"):
        await classify_actions(model_dict, test_frames)


# Test classify_actions top_k parameter


@pytest.mark.asyncio
async def test_classify_actions_top_k_validation():
    """Test classify_actions top_k parameter."""
    # Verify the default is 3
    import inspect

    sig = inspect.signature(classify_actions)
    assert sig.parameters["top_k"].default == 3


# Test security prompts completeness


def test_security_prompts_minimum_count():
    """Test that we have enough security prompts for coverage."""
    assert len(SECURITY_ACTION_PROMPTS) >= 10


def test_security_prompts_unique():
    """Test that all security prompts are unique."""
    assert len(SECURITY_ACTION_PROMPTS) == len(set(SECURITY_ACTION_PROMPTS))


# Test model_zoo integration


def test_xclip_in_model_zoo():
    """Test xclip-base is registered in MODEL_ZOO."""
    from backend.services.model_zoo import get_model_zoo

    zoo = get_model_zoo()
    assert "xclip-base" in zoo

    config = zoo["xclip-base"]
    assert config.name == "xclip-base"
    assert config.vram_mb == 2000
    assert config.category == "action-recognition"
