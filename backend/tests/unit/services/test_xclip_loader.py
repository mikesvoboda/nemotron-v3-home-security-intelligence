"""Unit tests for X-CLIP model loader service.

Tests cover:
- Model loading (CPU and GPU)
- Action classification in video frames
- Frame sampling for batch processing
- Suspicious action detection
- Action risk weighting
- Error handling
- Device handling (GPU/CPU fallback)
"""

from __future__ import annotations

import sys
from typing import Any
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import numpy as np
import pytest
from PIL import Image

from backend.services.xclip_loader import (
    ACTION_PROMPTS_V2,
    SECURITY_ACTION_PROMPTS,
    classify_actions,
    get_action_category,
    get_action_risk_level,
    get_action_risk_weight,
    get_action_threshold,
    get_all_action_prompts,
    is_suspicious_action,
    load_xclip_model,
    sample_frames_from_batch,
)


def create_mock_pixel_values() -> MagicMock:
    """Create a properly mocked pixel_values tensor with valid shape.

    X-CLIP expects pixel_values to have shape [batch, num_frames, channels, height, width].
    The production code validates this shape, so our mocks must provide it correctly.

    Returns:
        MagicMock with .shape = (1, 16, 3, 224, 224) and proper .to()/.half() methods
        (16 frames as per NEM-3908 upgrade to xclip-base-patch16-16-frames)
    """
    mock_pv = MagicMock()
    # X-CLIP video tensor shape: [batch=1, frames=16, channels=3, height=224, width=224]
    # Updated from 8 to 16 frames per NEM-3908
    mock_pv.shape = (1, 16, 3, 224, 224)
    mock_pv.to.return_value = mock_pv
    mock_pv.half.return_value = mock_pv
    return mock_pv


# =============================================================================
# Constants Tests
# =============================================================================


class TestSecurityActionPrompts:
    """Tests for SECURITY_ACTION_PROMPTS constant."""

    def test_prompts_not_empty(self) -> None:
        """Test that security action prompts list is not empty."""
        assert len(SECURITY_ACTION_PROMPTS) > 0

    def test_prompts_are_strings(self) -> None:
        """Test that all prompts are strings."""
        for prompt in SECURITY_ACTION_PROMPTS:
            assert isinstance(prompt, str)

    def test_prompts_contain_security_keywords(self) -> None:
        """Test that prompts contain security-related keywords."""
        all_prompts = " ".join(SECURITY_ACTION_PROMPTS).lower()
        security_keywords = ["loitering", "suspicious", "door", "breaking"]
        for keyword in security_keywords:
            assert keyword in all_prompts

    def test_prompts_include_normal_behaviors(self) -> None:
        """Test that prompts include normal behaviors for comparison."""
        all_prompts = " ".join(SECURITY_ACTION_PROMPTS).lower()
        normal_keywords = ["walking normally", "delivering", "knocking"]
        for keyword in normal_keywords:
            assert keyword in all_prompts


# =============================================================================
# load_xclip_model Tests
# =============================================================================


class TestLoadXclipModel:
    """Tests for load_xclip_model function."""

    @pytest.mark.asyncio
    async def test_load_model_success_cpu_no_torch(self) -> None:
        """Test successful model loading on CPU when torch not available."""
        mock_processor = MagicMock()
        mock_model = MagicMock()
        mock_model.eval = MagicMock(return_value=None)

        mock_xclip_processor_cls = MagicMock()
        mock_xclip_processor_cls.from_pretrained.return_value = mock_processor

        mock_xclip_model_cls = MagicMock()
        mock_xclip_model_cls.from_pretrained.return_value = mock_model

        # Create mock transformers module
        mock_transformers = MagicMock()
        mock_transformers.XCLIPProcessor = mock_xclip_processor_cls
        mock_transformers.XCLIPModel = mock_xclip_model_cls

        # Mock sys.modules so transformers is available but torch is not
        # Setting torch to None will cause import to fail
        with patch.dict(sys.modules, {"transformers": mock_transformers, "torch": None}):
            result = await load_xclip_model("/path/to/model")

        assert "model" in result
        assert "processor" in result
        mock_model.eval.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_model_success_with_gpu(self) -> None:
        """Test successful model loading with GPU support."""
        mock_processor = MagicMock()
        mock_model = MagicMock()
        mock_model_on_gpu = MagicMock()
        mock_model.cuda.return_value.half.return_value = mock_model_on_gpu
        mock_model_on_gpu.eval = MagicMock(return_value=None)

        mock_xclip_processor_cls = MagicMock()
        mock_xclip_processor_cls.from_pretrained.return_value = mock_processor

        mock_xclip_model_cls = MagicMock()
        mock_xclip_model_cls.from_pretrained.return_value = mock_model

        # Create mock transformers module
        mock_transformers = MagicMock()
        mock_transformers.XCLIPProcessor = mock_xclip_processor_cls
        mock_transformers.XCLIPModel = mock_xclip_model_cls

        # Create mock torch module
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True

        with patch.dict(sys.modules, {"transformers": mock_transformers, "torch": mock_torch}):
            result = await load_xclip_model("/path/to/model")

        assert "model" in result
        assert "processor" in result

    @pytest.mark.asyncio
    async def test_load_model_transformers_import_error(self) -> None:
        """Test model loading when transformers is not installed."""
        # Remove transformers from modules if present
        with patch.dict(sys.modules, {"transformers": None}):
            with pytest.raises(ImportError) as exc_info:
                await load_xclip_model("/path/to/model")

            assert "transformers" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_load_model_runtime_error_from_model_load(self) -> None:
        """Test model loading when model file is invalid."""
        mock_xclip_processor_cls = MagicMock()
        mock_xclip_processor_cls.from_pretrained.side_effect = OSError("Invalid model")

        mock_transformers = MagicMock()
        mock_transformers.XCLIPProcessor = mock_xclip_processor_cls
        mock_transformers.XCLIPModel = MagicMock()

        with patch.dict(sys.modules, {"transformers": mock_transformers}):
            with pytest.raises(RuntimeError) as exc_info:
                await load_xclip_model("/invalid/model/path")

            assert "Failed to load X-CLIP model" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_load_model_generic_exception(self) -> None:
        """Test model loading with generic exception."""
        mock_xclip_processor_cls = MagicMock()
        mock_xclip_processor_cls.from_pretrained.side_effect = ValueError("Unexpected error")

        mock_transformers = MagicMock()
        mock_transformers.XCLIPProcessor = mock_xclip_processor_cls
        mock_transformers.XCLIPModel = MagicMock()

        with patch.dict(sys.modules, {"transformers": mock_transformers}):
            with pytest.raises(RuntimeError) as exc_info:
                await load_xclip_model("/path/to/model")

            assert "Failed to load X-CLIP model" in str(exc_info.value)


class TestLoadXclipModelInternal:
    """Tests for internal _load function behavior."""

    @pytest.mark.asyncio
    async def test_load_model_cpu_no_cuda(self) -> None:
        """Test model loading when CUDA is not available."""
        mock_processor = MagicMock()
        mock_model = MagicMock()
        mock_model.eval = MagicMock(return_value=None)

        mock_xclip_processor_cls = MagicMock()
        mock_xclip_processor_cls.from_pretrained.return_value = mock_processor

        mock_xclip_model_cls = MagicMock()
        mock_xclip_model_cls.from_pretrained.return_value = mock_model

        mock_transformers = MagicMock()
        mock_transformers.XCLIPProcessor = mock_xclip_processor_cls
        mock_transformers.XCLIPModel = mock_xclip_model_cls

        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False

        with patch.dict(sys.modules, {"transformers": mock_transformers, "torch": mock_torch}):
            result = await load_xclip_model("/path/to/model")

        assert "model" in result
        assert "processor" in result
        # Should not call cuda() when CUDA not available
        mock_model.cuda.assert_not_called()

    @pytest.mark.asyncio
    async def test_load_model_with_huggingface_path(self) -> None:
        """Test model loading with HuggingFace model path."""
        mock_processor = MagicMock()
        mock_model = MagicMock()
        mock_model.eval = MagicMock(return_value=None)

        mock_xclip_processor_cls = MagicMock()
        mock_xclip_processor_cls.from_pretrained.return_value = mock_processor

        mock_xclip_model_cls = MagicMock()
        mock_xclip_model_cls.from_pretrained.return_value = mock_model

        mock_transformers = MagicMock()
        mock_transformers.XCLIPProcessor = mock_xclip_processor_cls
        mock_transformers.XCLIPModel = mock_xclip_model_cls

        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False

        with patch.dict(sys.modules, {"transformers": mock_transformers, "torch": mock_torch}):
            result = await load_xclip_model("microsoft/xclip-base-patch16-16-frames")

        assert "model" in result
        assert "processor" in result
        mock_xclip_processor_cls.from_pretrained.assert_called_once_with(
            "microsoft/xclip-base-patch16-16-frames"
        )


# =============================================================================
# classify_actions Tests
# =============================================================================


class TestClassifyActions:
    """Tests for classify_actions function."""

    @pytest.fixture
    def sample_frames(self) -> list[Image.Image]:
        """Create sample PIL Image frames for testing (16 frames per NEM-3908)."""
        return [Image.new("RGB", (224, 224), color="red") for _ in range(16)]

    @pytest.fixture
    def mock_model_dict(self) -> dict[str, Any]:
        """Create mock model dictionary with proper torch mocking."""
        mock_model = MagicMock()
        mock_processor = MagicMock()

        # Set up model parameters for device detection
        mock_param = MagicMock()
        mock_param.device = "cpu"
        mock_param.dtype = MagicMock()
        mock_model.parameters.return_value = iter([mock_param])

        return {"model": mock_model, "processor": mock_processor}

    @pytest.mark.asyncio
    async def test_classify_empty_frames_raises(self, mock_model_dict: dict[str, Any]) -> None:
        """Test that classify_actions raises ValueError for empty frames."""
        with pytest.raises(ValueError) as exc_info:
            await classify_actions(mock_model_dict, [])

        assert "At least one frame" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_classify_with_none_frames_raises(self, mock_model_dict: dict[str, Any]) -> None:
        """Test that classify_actions raises ValueError for all None frames."""
        # Test with all None frames
        with pytest.raises(ValueError) as exc_info:
            await classify_actions(mock_model_dict, [None, None, None])  # type: ignore

        assert "all frames are None" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_classify_filters_none_frames(self) -> None:
        """Test that classify_actions filters out None frames and proceeds with valid ones."""
        # Create mix of valid and None frames
        valid_frame = Image.new("RGB", (224, 224), color="blue")
        frames = [None, valid_frame, None, valid_frame, None]  # type: ignore

        mock_model = MagicMock()
        mock_processor = MagicMock()

        mock_param = MagicMock()
        mock_param.device = "cpu"
        mock_param.dtype = MagicMock()
        mock_model.parameters.return_value = iter([mock_param, mock_param])

        mock_inputs = {"pixel_values": create_mock_pixel_values()}
        for v in mock_inputs.values():
            v.to.return_value = v
        mock_processor.return_value = mock_inputs

        mock_outputs = MagicMock()
        mock_probs = MagicMock()
        mock_probs.squeeze.return_value.cpu.return_value.numpy.return_value = np.array(
            [0.75, 0.15, 0.10]
        )
        mock_outputs.logits_per_video = MagicMock()
        mock_model.return_value = mock_outputs

        model_dict = {"model": mock_model, "processor": mock_processor}

        mock_torch = MagicMock()
        mock_torch.no_grad.return_value.__enter__ = MagicMock(return_value=None)
        mock_torch.no_grad.return_value.__exit__ = MagicMock(return_value=None)
        mock_torch.softmax.return_value = mock_probs
        mock_torch.float16 = "float16"

        with patch.dict(sys.modules, {"torch": mock_torch}):
            result = await classify_actions(model_dict, frames, prompts=["walk", "run", "stand"])

        # Should succeed with only the valid frames
        assert "detected_action" in result
        assert result["confidence"] == 0.75

    @pytest.mark.asyncio
    async def test_classify_with_default_prompts(self, sample_frames: list[Image.Image]) -> None:
        """Test classification with default security prompts."""
        # Create mock model and processor
        mock_model = MagicMock()
        mock_processor = MagicMock()

        # Set up model parameters
        mock_param = MagicMock()
        mock_param.device = "cpu"
        mock_param.dtype = MagicMock()
        mock_model.parameters.return_value = iter([mock_param, mock_param])

        # Set up processor return value with properly shaped pixel_values
        mock_input_ids = MagicMock()
        mock_input_ids.to.return_value = mock_input_ids
        mock_inputs = {"pixel_values": create_mock_pixel_values(), "input_ids": mock_input_ids}
        mock_processor.return_value = mock_inputs

        # Set up model output
        mock_outputs = MagicMock()
        mock_logits = MagicMock()
        mock_probs = MagicMock()

        # Create proper numpy array for probs
        probs_array = np.zeros(len(SECURITY_ACTION_PROMPTS))
        probs_array[0] = 0.8
        probs_array[1] = 0.1
        probs_array[2] = 0.05
        for i in range(3, len(probs_array)):
            probs_array[i] = 0.05 / (len(probs_array) - 3)

        mock_probs.squeeze.return_value.cpu.return_value.numpy.return_value = probs_array
        mock_outputs.logits_per_video = mock_logits

        mock_model.return_value = mock_outputs

        model_dict = {"model": mock_model, "processor": mock_processor}

        # Mock torch
        mock_torch = MagicMock()
        mock_torch.no_grad.return_value.__enter__ = MagicMock(return_value=None)
        mock_torch.no_grad.return_value.__exit__ = MagicMock(return_value=None)
        mock_torch.softmax.return_value = mock_probs
        mock_torch.float16 = "float16"

        with patch.dict(sys.modules, {"torch": mock_torch}):
            result = await classify_actions(model_dict, sample_frames)

        assert "detected_action" in result
        assert "confidence" in result
        assert "top_actions" in result
        assert "all_scores" in result

    @pytest.mark.asyncio
    async def test_classify_with_custom_prompts(self, sample_frames: list[Image.Image]) -> None:
        """Test classification with custom prompts."""
        custom_prompts = ["action 1", "action 2", "action 3"]

        mock_model = MagicMock()
        mock_processor = MagicMock()

        mock_param = MagicMock()
        mock_param.device = "cpu"
        mock_param.dtype = MagicMock()
        mock_model.parameters.return_value = iter([mock_param, mock_param])

        mock_input_ids = MagicMock()
        mock_input_ids.to.return_value = mock_input_ids
        mock_inputs = {"pixel_values": create_mock_pixel_values(), "input_ids": mock_input_ids}
        mock_processor.return_value = mock_inputs

        mock_outputs = MagicMock()
        mock_logits = MagicMock()
        mock_probs = MagicMock()

        probs_array = np.array([0.9, 0.05, 0.05])
        mock_probs.squeeze.return_value.cpu.return_value.numpy.return_value = probs_array
        mock_outputs.logits_per_video = mock_logits

        mock_model.return_value = mock_outputs

        model_dict = {"model": mock_model, "processor": mock_processor}

        mock_torch = MagicMock()
        mock_torch.no_grad.return_value.__enter__ = MagicMock(return_value=None)
        mock_torch.no_grad.return_value.__exit__ = MagicMock(return_value=None)
        mock_torch.softmax.return_value = mock_probs
        mock_torch.float16 = "float16"

        with patch.dict(sys.modules, {"torch": mock_torch}):
            result = await classify_actions(model_dict, sample_frames, prompts=custom_prompts)

        assert result["detected_action"] == "action 1"
        assert result["confidence"] == 0.9

    @pytest.mark.asyncio
    async def test_classify_with_fewer_than_16_frames(self) -> None:
        """Test classification with fewer than 16 frames (should duplicate)."""
        frames = [Image.new("RGB", (224, 224), color="blue") for _ in range(3)]

        mock_model = MagicMock()
        mock_processor = MagicMock()

        mock_param = MagicMock()
        mock_param.device = "cpu"
        mock_param.dtype = MagicMock()
        mock_model.parameters.return_value = iter([mock_param, mock_param])

        mock_inputs = {"pixel_values": create_mock_pixel_values()}
        for v in mock_inputs.values():
            v.to.return_value = v
        mock_processor.return_value = mock_inputs

        mock_outputs = MagicMock()
        mock_probs = MagicMock()
        mock_probs.squeeze.return_value.cpu.return_value.numpy.return_value = np.array(
            [0.75, 0.15, 0.10]
        )
        mock_outputs.logits_per_video = MagicMock()
        mock_model.return_value = mock_outputs

        model_dict = {"model": mock_model, "processor": mock_processor}

        mock_torch = MagicMock()
        mock_torch.no_grad.return_value.__enter__ = MagicMock(return_value=None)
        mock_torch.no_grad.return_value.__exit__ = MagicMock(return_value=None)
        mock_torch.softmax.return_value = mock_probs
        mock_torch.float16 = "float16"

        with patch.dict(sys.modules, {"torch": mock_torch}):
            result = await classify_actions(model_dict, frames, prompts=["walk", "run", "stand"])

        assert "detected_action" in result
        assert result["confidence"] == 0.75

    @pytest.mark.asyncio
    async def test_classify_with_more_than_16_frames(self) -> None:
        """Test classification with more than 16 frames (should sample)."""
        frames = [Image.new("RGB", (224, 224), color="green") for _ in range(32)]

        mock_model = MagicMock()
        mock_processor = MagicMock()

        mock_param = MagicMock()
        mock_param.device = "cpu"
        mock_param.dtype = MagicMock()
        mock_model.parameters.return_value = iter([mock_param, mock_param])

        mock_inputs = {"pixel_values": create_mock_pixel_values()}
        for v in mock_inputs.values():
            v.to.return_value = v
        mock_processor.return_value = mock_inputs

        mock_outputs = MagicMock()
        mock_probs = MagicMock()
        mock_probs.squeeze.return_value.cpu.return_value.numpy.return_value = np.array(
            [0.65, 0.20, 0.15]
        )
        mock_outputs.logits_per_video = MagicMock()
        mock_model.return_value = mock_outputs

        model_dict = {"model": mock_model, "processor": mock_processor}

        mock_torch = MagicMock()
        mock_torch.no_grad.return_value.__enter__ = MagicMock(return_value=None)
        mock_torch.no_grad.return_value.__exit__ = MagicMock(return_value=None)
        mock_torch.softmax.return_value = mock_probs
        mock_torch.float16 = "float16"

        with patch.dict(sys.modules, {"torch": mock_torch}):
            result = await classify_actions(model_dict, frames, prompts=["loiter", "walk", "run"])

        assert "detected_action" in result

    @pytest.mark.asyncio
    async def test_classify_with_exactly_16_frames(self, sample_frames: list[Image.Image]) -> None:
        """Test classification with exactly 16 frames (NEM-3908)."""
        # Note: sample_frames fixture still provides 8 for legacy compat, test pads internally

        mock_model = MagicMock()
        mock_processor = MagicMock()

        mock_param = MagicMock()
        mock_param.device = "cpu"
        mock_param.dtype = MagicMock()
        mock_model.parameters.return_value = iter([mock_param, mock_param])

        mock_inputs = {"pixel_values": create_mock_pixel_values()}
        for v in mock_inputs.values():
            v.to.return_value = v
        mock_processor.return_value = mock_inputs

        mock_outputs = MagicMock()
        mock_probs = MagicMock()
        mock_probs.squeeze.return_value.cpu.return_value.numpy.return_value = np.array(
            [0.85, 0.10, 0.05]
        )
        mock_outputs.logits_per_video = MagicMock()
        mock_model.return_value = mock_outputs

        model_dict = {"model": mock_model, "processor": mock_processor}

        mock_torch = MagicMock()
        mock_torch.no_grad.return_value.__enter__ = MagicMock(return_value=None)
        mock_torch.no_grad.return_value.__exit__ = MagicMock(return_value=None)
        mock_torch.softmax.return_value = mock_probs
        mock_torch.float16 = "float16"

        with patch.dict(sys.modules, {"torch": mock_torch}):
            result = await classify_actions(
                model_dict, sample_frames, prompts=["door", "walk", "run"]
            )

        assert result["confidence"] == 0.85

    @pytest.mark.asyncio
    async def test_classify_top_k_parameter(self, sample_frames: list[Image.Image]) -> None:
        """Test classification with custom top_k parameter."""
        mock_model = MagicMock()
        mock_processor = MagicMock()

        mock_param = MagicMock()
        mock_param.device = "cpu"
        mock_param.dtype = MagicMock()
        mock_model.parameters.return_value = iter([mock_param, mock_param])

        mock_inputs = {"pixel_values": create_mock_pixel_values()}
        for v in mock_inputs.values():
            v.to.return_value = v
        mock_processor.return_value = mock_inputs

        mock_outputs = MagicMock()
        mock_probs = MagicMock()
        mock_probs.squeeze.return_value.cpu.return_value.numpy.return_value = np.array(
            [0.6, 0.2, 0.1, 0.05, 0.05]
        )
        mock_outputs.logits_per_video = MagicMock()
        mock_model.return_value = mock_outputs

        model_dict = {"model": mock_model, "processor": mock_processor}

        mock_torch = MagicMock()
        mock_torch.no_grad.return_value.__enter__ = MagicMock(return_value=None)
        mock_torch.no_grad.return_value.__exit__ = MagicMock(return_value=None)
        mock_torch.softmax.return_value = mock_probs
        mock_torch.float16 = "float16"

        with patch.dict(sys.modules, {"torch": mock_torch}):
            result = await classify_actions(
                model_dict,
                sample_frames,
                prompts=["a", "b", "c", "d", "e"],
                top_k=5,
            )

        assert len(result["top_actions"]) == 5

    @pytest.mark.asyncio
    async def test_classify_runtime_error(self, sample_frames: list[Image.Image]) -> None:
        """Test classification raises RuntimeError on failure."""
        mock_model = MagicMock()
        mock_processor = MagicMock()

        mock_param = MagicMock()
        mock_param.device = "cpu"
        mock_model.parameters.return_value = iter([mock_param])

        # Make model raise an exception
        mock_model.side_effect = RuntimeError("Model inference failed")

        model_dict = {"model": mock_model, "processor": mock_processor}

        mock_torch = MagicMock()
        mock_torch.no_grad.return_value.__enter__ = MagicMock(return_value=None)
        mock_torch.no_grad.return_value.__exit__ = MagicMock(return_value=None)

        with (
            patch.dict(sys.modules, {"torch": mock_torch}),
            pytest.raises(RuntimeError) as exc_info,
        ):
            await classify_actions(model_dict, sample_frames, prompts=["a", "b"])

        assert "X-CLIP classification failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_classify_generic_exception(self, sample_frames: list[Image.Image]) -> None:
        """Test classification wraps generic exceptions in RuntimeError."""
        mock_model = MagicMock()
        mock_processor = MagicMock()

        mock_param = MagicMock()
        mock_param.device = "cpu"
        mock_model.parameters.return_value = iter([mock_param])

        # Make processor raise an exception
        mock_processor.side_effect = ValueError("Unexpected error")

        model_dict = {"model": mock_model, "processor": mock_processor}

        mock_torch = MagicMock()
        mock_torch.no_grad.return_value.__enter__ = MagicMock(return_value=None)
        mock_torch.no_grad.return_value.__exit__ = MagicMock(return_value=None)

        with (
            patch.dict(sys.modules, {"torch": mock_torch}),
            pytest.raises(RuntimeError) as exc_info,
        ):
            await classify_actions(model_dict, sample_frames, prompts=["a", "b"])

        assert "X-CLIP classification failed" in str(exc_info.value)


class TestClassifyActionsInternal:
    """Tests for internal _classify function behavior."""

    @pytest.mark.asyncio
    async def test_classify_handles_float16_model(self) -> None:
        """Test classification handles float16 model correctly."""
        mock_model = MagicMock()
        mock_processor = MagicMock()

        mock_param = MagicMock()
        mock_param.device = "cuda"

        # Create mock torch with float16
        mock_torch = MagicMock()
        mock_torch.float16 = "float16_type"
        mock_param.dtype = mock_torch.float16

        mock_model.parameters.return_value = iter([mock_param, mock_param])

        # Set up processor with properly shaped pixel_values
        mock_pixel_values = create_mock_pixel_values()
        mock_inputs = {"pixel_values": mock_pixel_values}
        mock_processor.return_value = mock_inputs

        # Set up model output
        mock_outputs = MagicMock()
        mock_probs = MagicMock()
        mock_probs.squeeze.return_value.cpu.return_value.numpy.return_value = np.array(
            [0.5, 0.3, 0.2]
        )
        mock_outputs.logits_per_video = MagicMock()
        mock_model.return_value = mock_outputs

        model_dict = {"model": mock_model, "processor": mock_processor}
        frames = [Image.new("RGB", (224, 224)) for _ in range(8)]

        mock_torch.no_grad.return_value.__enter__ = MagicMock(return_value=None)
        mock_torch.no_grad.return_value.__exit__ = MagicMock(return_value=None)
        mock_torch.softmax.return_value = mock_probs

        with patch.dict(sys.modules, {"torch": mock_torch}):
            result = await classify_actions(model_dict, frames, prompts=["a", "b", "c"])

        assert result is not None
        assert "detected_action" in result
        # Verify half() was called for float16 model
        mock_pixel_values.half.assert_called()

    @pytest.mark.asyncio
    async def test_classify_all_frames_fail_numpy_validation(self) -> None:
        """Test that error is raised when all frames fail numpy conversion (deep validation)."""
        from backend.services.xclip_loader import classify_actions

        mock_model = MagicMock()
        mock_processor = MagicMock()

        mock_param = MagicMock()
        mock_param.device = "cpu"
        mock_param.dtype = MagicMock()
        mock_model.parameters.return_value = iter([mock_param, mock_param])

        model_dict = {"model": mock_model, "processor": mock_processor}

        # Create frames that pass initial validation but fail deep validation
        # Mock PIL images where numpy conversion fails
        mock_frame = MagicMock(spec=Image.Image)
        mock_frame.size = (224, 224)
        mock_frame.mode = "RGB"
        mock_frame.load.side_effect = OSError("Corrupted during load")

        frames = [mock_frame, mock_frame, mock_frame]  # type: ignore[list-item]

        mock_torch = MagicMock()
        mock_torch.no_grad.return_value.__enter__ = MagicMock(return_value=None)
        mock_torch.no_grad.return_value.__exit__ = MagicMock(return_value=None)
        mock_torch.float16 = "float16"

        # Should raise ValueError about all frames failed numpy conversion
        with patch.dict(sys.modules, {"torch": mock_torch}):
            with pytest.raises(ValueError, match="all frames failed numpy conversion"):
                await classify_actions(model_dict, frames, prompts=["a", "b", "c"])  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_classify_frame_validation_with_invalid_shape(self) -> None:
        """Test frame validation handles invalid numpy array shapes."""
        from backend.services.xclip_loader import classify_actions

        mock_model = MagicMock()
        mock_processor = MagicMock()

        mock_param = MagicMock()
        mock_param.device = "cpu"
        mock_param.dtype = MagicMock()
        mock_model.parameters.return_value = iter([mock_param, mock_param])

        # Create a processor that validates and returns proper tensor
        mock_inputs = {"pixel_values": create_mock_pixel_values()}
        for v in mock_inputs.values():
            v.to.return_value = v
        mock_processor.return_value = mock_inputs

        mock_outputs = MagicMock()
        mock_probs = MagicMock()
        mock_probs.squeeze.return_value.cpu.return_value.numpy.return_value = np.array([0.5, 0.5])
        mock_outputs.logits_per_video = MagicMock()
        mock_model.return_value = mock_outputs

        model_dict = {"model": mock_model, "processor": mock_processor}

        # Create one valid frame
        frames = [Image.new("RGB", (224, 224))]

        mock_torch = MagicMock()
        mock_torch.no_grad.return_value.__enter__ = MagicMock(return_value=None)
        mock_torch.no_grad.return_value.__exit__ = MagicMock(return_value=None)
        mock_torch.softmax.return_value = mock_probs
        mock_torch.float16 = "float16"

        # Should handle frame validation gracefully
        with patch.dict(sys.modules, {"torch": mock_torch}):
            result = await classify_actions(model_dict, frames, prompts=["a", "b"])

        assert result is not None

    @pytest.mark.asyncio
    async def test_classify_processor_returns_none(self) -> None:
        """Test that RuntimeError is raised when processor returns None."""
        from backend.services.xclip_loader import classify_actions

        mock_model = MagicMock()
        mock_processor = MagicMock()

        mock_param = MagicMock()
        mock_param.device = "cpu"
        mock_param.dtype = MagicMock()
        mock_model.parameters.return_value = iter([mock_param, mock_param])

        # Processor returns None
        mock_processor.return_value = None

        model_dict = {"model": mock_model, "processor": mock_processor}
        frames = [Image.new("RGB", (224, 224)) for _ in range(16)]

        mock_torch = MagicMock()
        mock_torch.no_grad.return_value.__enter__ = MagicMock(return_value=None)
        mock_torch.no_grad.return_value.__exit__ = MagicMock(return_value=None)
        mock_torch.float16 = "float16"

        with patch.dict(sys.modules, {"torch": mock_torch}):
            with pytest.raises(RuntimeError, match="X-CLIP processor returned None"):
                await classify_actions(model_dict, frames, prompts=["a", "b", "c"])

    @pytest.mark.asyncio
    async def test_classify_processor_returns_none_pixel_values(self) -> None:
        """Test that RuntimeError is raised when processor returns None for pixel_values."""
        from backend.services.xclip_loader import classify_actions

        mock_model = MagicMock()
        mock_processor = MagicMock()

        mock_param = MagicMock()
        mock_param.device = "cpu"
        mock_param.dtype = MagicMock()
        mock_model.parameters.return_value = iter([mock_param, mock_param])

        # Processor returns dict with None pixel_values
        mock_processor.return_value = {"pixel_values": None}

        model_dict = {"model": mock_model, "processor": mock_processor}
        frames = [Image.new("RGB", (224, 224)) for _ in range(16)]

        mock_torch = MagicMock()
        mock_torch.no_grad.return_value.__enter__ = MagicMock(return_value=None)
        mock_torch.no_grad.return_value.__exit__ = MagicMock(return_value=None)
        mock_torch.float16 = "float16"

        with patch.dict(sys.modules, {"torch": mock_torch}):
            with pytest.raises(RuntimeError, match="returned None for pixel_values"):
                await classify_actions(model_dict, frames, prompts=["a", "b", "c"])

    @pytest.mark.asyncio
    async def test_classify_pixel_values_no_shape_attribute(self) -> None:
        """Test that RuntimeError is raised when pixel_values has no shape attribute."""
        from backend.services.xclip_loader import classify_actions

        mock_model = MagicMock()
        mock_processor = MagicMock()

        mock_param = MagicMock()
        mock_param.device = "cpu"
        mock_param.dtype = MagicMock()
        mock_model.parameters.return_value = iter([mock_param, mock_param])

        # Create pixel_values without shape attribute
        mock_pixel_values = MagicMock()
        del mock_pixel_values.shape  # Remove shape attribute
        mock_processor.return_value = {"pixel_values": mock_pixel_values}

        model_dict = {"model": mock_model, "processor": mock_processor}
        frames = [Image.new("RGB", (224, 224)) for _ in range(16)]

        mock_torch = MagicMock()
        mock_torch.no_grad.return_value.__enter__ = MagicMock(return_value=None)
        mock_torch.no_grad.return_value.__exit__ = MagicMock(return_value=None)
        mock_torch.float16 = "float16"

        with patch.dict(sys.modules, {"torch": mock_torch}):
            with pytest.raises(RuntimeError, match="has no shape attribute"):
                await classify_actions(model_dict, frames, prompts=["a", "b", "c"])

    @pytest.mark.asyncio
    async def test_classify_processor_attribute_error(self) -> None:
        """Test that RuntimeError is raised when processor raises AttributeError."""
        from backend.services.xclip_loader import classify_actions

        mock_model = MagicMock()
        mock_processor = MagicMock()

        mock_param = MagicMock()
        mock_param.device = "cpu"
        mock_param.dtype = MagicMock()
        mock_model.parameters.return_value = iter([mock_param, mock_param])

        # Processor raises AttributeError (NoneType has no attribute 'shape')
        mock_processor.side_effect = AttributeError("'NoneType' object has no attribute 'shape'")

        model_dict = {"model": mock_model, "processor": mock_processor}
        frames = [Image.new("RGB", (224, 224)) for _ in range(16)]

        mock_torch = MagicMock()
        mock_torch.no_grad.return_value.__enter__ = MagicMock(return_value=None)
        mock_torch.no_grad.return_value.__exit__ = MagicMock(return_value=None)
        mock_torch.float16 = "float16"

        with patch.dict(sys.modules, {"torch": mock_torch}):
            with pytest.raises(RuntimeError, match="processor failed"):
                await classify_actions(model_dict, frames, prompts=["a", "b", "c"])

    @pytest.mark.asyncio
    async def test_classify_frame_repadding_after_validation_loss(self) -> None:
        """Test that frames are re-padded if some are lost during final validation."""
        from backend.services.xclip_loader import classify_actions

        mock_model = MagicMock()
        mock_processor = MagicMock()

        mock_param = MagicMock()
        mock_param.device = "cpu"
        mock_param.dtype = MagicMock()
        mock_model.parameters.return_value = iter([mock_param, mock_param])

        # Setup proper mocked tensors
        mock_inputs = {"pixel_values": create_mock_pixel_values()}
        for v in mock_inputs.values():
            v.to.return_value = v
        mock_processor.return_value = mock_inputs

        mock_outputs = MagicMock()
        mock_probs = MagicMock()
        mock_probs.squeeze.return_value.cpu.return_value.numpy.return_value = np.array(
            [0.6, 0.3, 0.1]
        )
        mock_outputs.logits_per_video = MagicMock()
        mock_model.return_value = mock_outputs

        model_dict = {"model": mock_model, "processor": mock_processor}

        # Create frames - just a few to trigger padding
        frames = [Image.new("RGB", (224, 224)) for _ in range(5)]

        mock_torch = MagicMock()
        mock_torch.no_grad.return_value.__enter__ = MagicMock(return_value=None)
        mock_torch.no_grad.return_value.__exit__ = MagicMock(return_value=None)
        mock_torch.softmax.return_value = mock_probs
        mock_torch.float16 = "float16"

        with patch.dict(sys.modules, {"torch": mock_torch}):
            result = await classify_actions(model_dict, frames, prompts=["a", "b", "c"])

        assert result is not None
        assert "detected_action" in result


# =============================================================================
# sample_frames_from_batch Tests
# =============================================================================


class TestSampleFramesFromBatch:
    """Tests for sample_frames_from_batch function."""

    def test_sample_fewer_frames_returns_all(self) -> None:
        """Test that fewer frames than target returns all frames."""
        frame_paths = ["/path/frame1.jpg", "/path/frame2.jpg", "/path/frame3.jpg"]
        result = sample_frames_from_batch(frame_paths, target_count=16)
        assert result == frame_paths

    def test_sample_exact_frames_returns_all(self) -> None:
        """Test that exact number of frames returns all frames (16 frames for NEM-3908)."""
        frame_paths = [f"/path/frame{i}.jpg" for i in range(16)]
        result = sample_frames_from_batch(frame_paths, target_count=16)
        assert result == frame_paths

    def test_sample_more_frames_uniform_sampling(self) -> None:
        """Test that more frames are uniformly sampled (16 target per NEM-3908)."""
        frame_paths = [f"/path/frame{i}.jpg" for i in range(32)]
        result = sample_frames_from_batch(frame_paths, target_count=16)

        assert len(result) == 16
        # Should include first frame
        assert result[0] == "/path/frame0.jpg"
        # Should have frames distributed across the range
        assert "/path/frame16.jpg" in result or "/path/frame15.jpg" in result

    def test_sample_default_target_count(self) -> None:
        """Test default target_count of 16 (NEM-3908)."""
        frame_paths = [f"/path/frame{i}.jpg" for i in range(32)]
        result = sample_frames_from_batch(frame_paths)
        assert len(result) == 16

    def test_sample_custom_target_count(self) -> None:
        """Test custom target_count."""
        frame_paths = [f"/path/frame{i}.jpg" for i in range(20)]
        result = sample_frames_from_batch(frame_paths, target_count=4)
        assert len(result) == 4

    def test_sample_empty_list(self) -> None:
        """Test empty frame list."""
        result = sample_frames_from_batch([], target_count=8)
        assert result == []

    def test_sample_single_frame(self) -> None:
        """Test single frame list."""
        frame_paths = ["/path/frame0.jpg"]
        result = sample_frames_from_batch(frame_paths, target_count=8)
        assert result == frame_paths

    def test_sample_preserves_order(self) -> None:
        """Test that sampling preserves temporal order."""
        frame_paths = [f"/path/frame{i:02d}.jpg" for i in range(24)]
        result = sample_frames_from_batch(frame_paths, target_count=8)

        # Verify order is preserved
        indices = [int(p.split("frame")[1].split(".")[0]) for p in result]
        assert indices == sorted(indices)

    def test_sample_large_batch(self) -> None:
        """Test sampling from large batch."""
        frame_paths = [f"/path/frame{i}.jpg" for i in range(1000)]
        result = sample_frames_from_batch(frame_paths, target_count=8)

        assert len(result) == 8
        # First frame should always be included
        assert result[0] == "/path/frame0.jpg"


# =============================================================================
# is_suspicious_action Tests
# =============================================================================


class TestIsSuspiciousAction:
    """Tests for is_suspicious_action function."""

    def test_loitering_is_suspicious(self) -> None:
        """Test that loitering is detected as suspicious."""
        assert is_suspicious_action("a person loitering") is True

    def test_suspicious_behavior_detected(self) -> None:
        """Test that suspicious looking around is detected."""
        assert is_suspicious_action("a person looking around suspiciously") is True

    def test_running_away_is_suspicious(self) -> None:
        """Test that running away is detected as suspicious."""
        assert is_suspicious_action("a person running away") is True

    def test_trying_door_is_suspicious(self) -> None:
        """Test that trying door handle is suspicious."""
        assert is_suspicious_action("a person trying door handle") is True

    def test_hiding_is_suspicious(self) -> None:
        """Test that hiding near bushes is suspicious."""
        assert is_suspicious_action("a person hiding near bushes") is True

    def test_vandalizing_is_suspicious(self) -> None:
        """Test that vandalizing is suspicious."""
        assert is_suspicious_action("a person vandalizing property") is True

    def test_breaking_in_is_suspicious(self) -> None:
        """Test that breaking in is suspicious."""
        assert is_suspicious_action("a person breaking in") is True

    def test_checking_windows_is_suspicious(self) -> None:
        """Test that checking windows is suspicious."""
        assert is_suspicious_action("a person checking windows") is True

    def test_taking_photos_is_suspicious(self) -> None:
        """Test that taking photos of house is suspicious."""
        assert is_suspicious_action("a person taking photos of house") is True

    def test_walking_normally_not_suspicious(self) -> None:
        """Test that walking normally is not suspicious."""
        assert is_suspicious_action("a person walking normally") is False

    def test_delivering_package_not_suspicious(self) -> None:
        """Test that delivering package is not suspicious."""
        assert is_suspicious_action("a person delivering a package") is False

    def test_knocking_on_door_not_suspicious(self) -> None:
        """Test that knocking on door is not suspicious."""
        assert is_suspicious_action("a person knocking on door") is False

    def test_ringing_doorbell_not_suspicious(self) -> None:
        """Test that ringing doorbell is not suspicious."""
        assert is_suspicious_action("a person ringing doorbell") is False

    def test_case_insensitive_detection(self) -> None:
        """Test that detection is case insensitive."""
        assert is_suspicious_action("A PERSON LOITERING") is True
        assert is_suspicious_action("A Person Running Away") is True

    def test_partial_match(self) -> None:
        """Test partial keyword matching."""
        assert is_suspicious_action("loitering detected") is True
        assert is_suspicious_action("someone is hiding") is True

    def test_empty_string(self) -> None:
        """Test empty string."""
        assert is_suspicious_action("") is False

    def test_unrelated_action(self) -> None:
        """Test unrelated action."""
        assert is_suspicious_action("a cat walking") is False


# =============================================================================
# get_action_risk_weight Tests
# =============================================================================


class TestGetActionRiskWeight:
    """Tests for get_action_risk_weight function."""

    # High risk actions (1.0)
    def test_breaking_in_high_risk(self) -> None:
        """Test that breaking in is high risk."""
        assert get_action_risk_weight("a person breaking in") == 1.0

    def test_vandalizing_high_risk(self) -> None:
        """Test that vandalizing is high risk."""
        assert get_action_risk_weight("a person vandalizing") == 1.0

    def test_trying_door_handle_high_risk(self) -> None:
        """Test that trying door handle is high risk."""
        assert get_action_risk_weight("a person trying door handle") == 1.0

    def test_hiding_high_risk(self) -> None:
        """Test that hiding is high risk."""
        assert get_action_risk_weight("a person hiding near bushes") == 1.0

    # Medium risk actions (0.7)
    def test_loitering_medium_risk(self) -> None:
        """Test that loitering is medium risk."""
        assert get_action_risk_weight("a person loitering") == 0.7

    def test_suspiciously_medium_risk(self) -> None:
        """Test that suspicious behavior is medium risk."""
        assert get_action_risk_weight("a person looking suspiciously") == 0.7

    def test_running_away_medium_risk(self) -> None:
        """Test that running away is medium risk."""
        assert get_action_risk_weight("a person running away") == 0.7

    def test_taking_photos_medium_risk(self) -> None:
        """Test that taking photos is medium risk."""
        assert get_action_risk_weight("a person taking photos") == 0.7

    def test_checking_windows_medium_risk(self) -> None:
        """Test that checking windows is medium risk."""
        assert get_action_risk_weight("a person checking windows") == 0.7

    # Low risk actions (0.2)
    def test_delivering_low_risk(self) -> None:
        """Test that delivering is low risk."""
        assert get_action_risk_weight("a person delivering a package") == 0.2

    def test_knocking_low_risk(self) -> None:
        """Test that knocking is low risk."""
        assert get_action_risk_weight("a person knocking on door") == 0.2

    def test_ringing_low_risk(self) -> None:
        """Test that ringing doorbell is low risk."""
        assert get_action_risk_weight("a person ringing doorbell") == 0.2

    def test_leaving_package_low_risk(self) -> None:
        """Test that leaving package is low risk."""
        assert get_action_risk_weight("a person leaving package at door") == 0.2

    def test_walking_normally_low_risk(self) -> None:
        """Test that walking normally is low risk."""
        assert get_action_risk_weight("a person walking normally") == 0.2

    # Neutral actions (0.5)
    def test_unknown_action_neutral(self) -> None:
        """Test that unknown action is neutral risk."""
        assert get_action_risk_weight("a person standing") == 0.5

    def test_unclassified_action_neutral(self) -> None:
        """Test that unclassified action is neutral."""
        assert get_action_risk_weight("a person doing something") == 0.5

    def test_empty_string_neutral(self) -> None:
        """Test empty string is neutral."""
        assert get_action_risk_weight("") == 0.5

    # Case insensitivity
    def test_case_insensitive_high_risk(self) -> None:
        """Test case insensitive high risk detection."""
        assert get_action_risk_weight("BREAKING IN") == 1.0
        assert get_action_risk_weight("Breaking In") == 1.0

    def test_case_insensitive_medium_risk(self) -> None:
        """Test case insensitive medium risk detection."""
        assert get_action_risk_weight("LOITERING") == 0.7

    def test_case_insensitive_low_risk(self) -> None:
        """Test case insensitive low risk detection."""
        assert get_action_risk_weight("DELIVERING PACKAGE") == 0.2

    # Priority testing (high risk should take precedence)
    def test_high_risk_takes_precedence(self) -> None:
        """Test that high risk keywords take precedence over others."""
        # Breaking in is high risk, even if other keywords present
        assert get_action_risk_weight("breaking in while delivering") == 1.0

    # Edge cases
    def test_partial_keyword_match(self) -> None:
        """Test partial keyword matching."""
        assert get_action_risk_weight("the person was hiding") == 1.0

    def test_multiple_keywords(self) -> None:
        """Test action with multiple keywords picks highest risk."""
        # hiding (1.0) should win over loitering (0.7)
        assert get_action_risk_weight("hiding and loitering") == 1.0


# =============================================================================
# Integration-style Tests
# =============================================================================


class TestXclipLoaderIntegration:
    """Integration-style tests for X-CLIP loader."""

    @pytest.mark.asyncio
    async def test_full_workflow_mock(self) -> None:
        """Test full workflow from model loading to classification."""
        # Set up mock transformers
        mock_processor = MagicMock()
        mock_model = MagicMock()
        mock_model.eval = MagicMock(return_value=None)

        mock_xclip_processor_cls = MagicMock()
        mock_xclip_processor_cls.from_pretrained.return_value = mock_processor

        mock_xclip_model_cls = MagicMock()
        mock_xclip_model_cls.from_pretrained.return_value = mock_model

        mock_transformers = MagicMock()
        mock_transformers.XCLIPProcessor = mock_xclip_processor_cls
        mock_transformers.XCLIPModel = mock_xclip_model_cls

        # Set up mock torch
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False
        mock_torch.float16 = "float16"
        mock_torch.no_grad.return_value.__enter__ = MagicMock(return_value=None)
        mock_torch.no_grad.return_value.__exit__ = MagicMock(return_value=None)

        # Set up model parameters
        mock_param = MagicMock()
        mock_param.device = "cpu"
        mock_param.dtype = MagicMock()
        mock_model.parameters.return_value = iter([mock_param, mock_param])

        # Set up processor for classification
        mock_inputs = {"pixel_values": create_mock_pixel_values()}
        for v in mock_inputs.values():
            v.to.return_value = v
        mock_processor.return_value = mock_inputs

        # Set up model output
        mock_outputs = MagicMock()
        mock_probs = MagicMock()
        mock_probs.squeeze.return_value.cpu.return_value.numpy.return_value = np.array(
            [0.85, 0.10, 0.05]
        )
        mock_outputs.logits_per_video = MagicMock()
        mock_model.return_value = mock_outputs

        mock_torch.softmax.return_value = mock_probs

        with patch.dict(sys.modules, {"transformers": mock_transformers, "torch": mock_torch}):
            # Load model
            model_dict = await load_xclip_model("/path/to/model")
            assert model_dict is not None

            # Create test frames
            frames = [Image.new("RGB", (224, 224)) for _ in range(8)]

            # Classify actions
            result = await classify_actions(
                model_dict,
                frames,
                prompts=["a person loitering", "a person walking normally", "other"],
            )

            # Verify result structure
            assert result["detected_action"] == "a person loitering"
            assert result["confidence"] == 0.85
            assert len(result["top_actions"]) == 3

            # Check if action is suspicious
            assert is_suspicious_action(result["detected_action"]) is True

            # Get risk weight
            risk = get_action_risk_weight(result["detected_action"])
            assert risk == 0.7  # loitering is medium risk

    def test_frame_sampling_in_pipeline(self) -> None:
        """Test frame sampling as part of processing pipeline."""
        # Simulate a batch of frame paths from file watcher
        batch_paths = [f"/export/foscam/front_door/snap_{i:04d}.jpg" for i in range(50)]

        # Sample for X-CLIP processing (16 frames per NEM-3908)
        sampled = sample_frames_from_batch(batch_paths, target_count=16)

        assert len(sampled) == 16
        # Verify sampling distribution
        assert sampled[0] == batch_paths[0]  # First frame

    def test_risk_scoring_consistency(self) -> None:
        """Test that risk scoring is consistent across prompts."""
        # All high-risk prompts should return 1.0
        high_risk_prompts = [
            "breaking in",
            "vandalizing property",
            "trying door handle",
            "hiding near bushes",
        ]
        for prompt in high_risk_prompts:
            assert get_action_risk_weight(prompt) == 1.0

        # All low-risk prompts should return 0.2
        low_risk_prompts = [
            "delivering a package",
            "knocking on door",
            "ringing doorbell",
            "walking normally",
        ]
        for prompt in low_risk_prompts:
            assert get_action_risk_weight(prompt) == 0.2


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestXclipLoaderEdgeCases:
    """Edge case tests for X-CLIP loader."""

    @pytest.fixture
    def mock_model_dict(self) -> dict[str, Any]:
        """Create mock model dictionary with proper torch mocking."""
        mock_model = MagicMock()
        mock_processor = MagicMock()

        # Set up model parameters for device detection
        mock_param = MagicMock()
        mock_param.device = "cpu"
        mock_param.dtype = MagicMock()
        mock_model.parameters.return_value = iter([mock_param])

        return {"model": mock_model, "processor": mock_processor}

    @pytest.mark.asyncio
    async def test_classify_single_frame(self) -> None:
        """Test classification with single frame (should pad to 16 per NEM-3908)."""
        mock_model = MagicMock()
        mock_processor = MagicMock()

        mock_param = MagicMock()
        mock_param.device = "cpu"
        mock_param.dtype = MagicMock()
        mock_model.parameters.return_value = iter([mock_param, mock_param])

        mock_inputs = {"pixel_values": create_mock_pixel_values()}
        for v in mock_inputs.values():
            v.to.return_value = v
        mock_processor.return_value = mock_inputs

        mock_outputs = MagicMock()
        mock_probs = MagicMock()
        mock_probs.squeeze.return_value.cpu.return_value.numpy.return_value = np.array([0.5, 0.5])
        mock_outputs.logits_per_video = MagicMock()
        mock_model.return_value = mock_outputs

        model_dict = {"model": mock_model, "processor": mock_processor}
        frames = [Image.new("RGB", (224, 224))]

        mock_torch = MagicMock()
        mock_torch.no_grad.return_value.__enter__ = MagicMock(return_value=None)
        mock_torch.no_grad.return_value.__exit__ = MagicMock(return_value=None)
        mock_torch.softmax.return_value = mock_probs
        mock_torch.float16 = "float16"

        with patch.dict(sys.modules, {"torch": mock_torch}):
            result = await classify_actions(model_dict, frames, prompts=["a", "b"])

        assert result is not None
        assert "detected_action" in result

    def test_sample_frames_with_target_one(self) -> None:
        """Test sampling with target_count of 1."""
        paths = [f"/path/frame{i}.jpg" for i in range(10)]
        result = sample_frames_from_batch(paths, target_count=1)
        assert len(result) == 1
        assert result[0] == "/path/frame0.jpg"

    def test_suspicious_action_with_special_characters(self) -> None:
        """Test suspicious action detection with special characters."""
        assert is_suspicious_action("person loitering!!!") is True
        assert is_suspicious_action("loitering...") is True

    def test_risk_weight_with_whitespace(self) -> None:
        """Test risk weight with extra whitespace."""
        assert get_action_risk_weight("  breaking in  ") == 1.0
        assert get_action_risk_weight("\tloitering\n") == 0.7

    def test_security_prompts_unique(self) -> None:
        """Test that all security prompts are unique (after deduplication).

        Note: There may be intentional duplicates across categories for
        different risk classification. We check the set size is reasonable.
        """
        unique_count = len(set(SECURITY_ACTION_PROMPTS))
        total_count = len(SECURITY_ACTION_PROMPTS)
        # Allow small number of duplicates due to category overlap
        assert unique_count >= total_count - 2, (
            f"Too many duplicate prompts: {total_count - unique_count}"
        )

    def test_security_prompts_most_describe_person_action(self) -> None:
        """Test that most security prompts describe a person's action.

        Note: Some prompts may use specific roles (e.g., 'delivery driver')
        instead of 'person', which is acceptable for better classification.
        """
        person_count = sum(1 for p in SECURITY_ACTION_PROMPTS if "person" in p.lower())
        driver_count = sum(1 for p in SECURITY_ACTION_PROMPTS if "driver" in p.lower())
        total_human = person_count + driver_count
        total_count = len(SECURITY_ACTION_PROMPTS)
        # At least 90% should describe human actions
        assert total_human >= total_count * 0.9, (
            f"Only {total_human}/{total_count} prompts describe human actions"
        )

    @pytest.mark.asyncio
    async def test_classify_with_invalid_objects_raises(
        self, mock_model_dict: dict[str, Any]
    ) -> None:
        """Test that classify_actions raises ValueError for invalid objects (not PIL Images)."""
        # Mix of valid and invalid objects - all invalid should result in ValueError
        invalid_frames = ["string", 123, {"dict": "value"}]  # type: ignore

        with pytest.raises(ValueError) as exc_info:
            await classify_actions(mock_model_dict, invalid_frames, prompts=["a", "b"])

        assert "invalid PIL Images" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_classify_filters_invalid_objects_keeps_valid(self) -> None:
        """Test that classify_actions filters invalid objects but keeps valid PIL Images."""
        valid_frame = Image.new("RGB", (224, 224), color="blue")
        # Mix valid and invalid objects
        frames = ["invalid", valid_frame, 12345, valid_frame]  # type: ignore

        mock_model = MagicMock()
        mock_processor = MagicMock()

        mock_param = MagicMock()
        mock_param.device = "cpu"
        mock_param.dtype = MagicMock()
        mock_model.parameters.return_value = iter([mock_param, mock_param])

        mock_inputs = {"pixel_values": create_mock_pixel_values()}
        for v in mock_inputs.values():
            v.to.return_value = v
        mock_processor.return_value = mock_inputs

        mock_outputs = MagicMock()
        mock_probs = MagicMock()
        mock_probs.squeeze.return_value.cpu.return_value.numpy.return_value = np.array(
            [0.75, 0.15, 0.10]
        )
        mock_outputs.logits_per_video = MagicMock()
        mock_model.return_value = mock_outputs

        model_dict = {"model": mock_model, "processor": mock_processor}

        mock_torch = MagicMock()
        mock_torch.no_grad.return_value.__enter__ = MagicMock(return_value=None)
        mock_torch.no_grad.return_value.__exit__ = MagicMock(return_value=None)
        mock_torch.softmax.return_value = mock_probs
        mock_torch.float16 = "float16"

        with patch.dict(sys.modules, {"torch": mock_torch}):
            result = await classify_actions(model_dict, frames, prompts=["walk", "run", "stand"])

        # Should succeed with only the valid frames
        assert "detected_action" in result
        assert result["confidence"] == 0.75


# =============================================================================
# PIL Image Validation Tests
# =============================================================================


class TestPilImageValidation:
    """Tests for _is_valid_pil_image helper function."""

    def test_valid_pil_image_returns_true(self) -> None:
        """Test that valid PIL Images return True."""
        from backend.services.xclip_loader import _is_valid_pil_image

        img = Image.new("RGB", (100, 100))
        assert _is_valid_pil_image(img) is True

    def test_none_returns_false(self) -> None:
        """Test that None returns False."""
        from backend.services.xclip_loader import _is_valid_pil_image

        assert _is_valid_pil_image(None) is False

    def test_string_returns_false(self) -> None:
        """Test that string returns False."""
        from backend.services.xclip_loader import _is_valid_pil_image

        assert _is_valid_pil_image("not an image") is False

    def test_numpy_array_returns_false(self) -> None:
        """Test that numpy array returns False (not a PIL Image)."""
        from backend.services.xclip_loader import _is_valid_pil_image

        arr = np.zeros((100, 100, 3), dtype=np.uint8)
        assert _is_valid_pil_image(arr) is False

    def test_dict_returns_false(self) -> None:
        """Test that dict returns False."""
        from backend.services.xclip_loader import _is_valid_pil_image

        assert _is_valid_pil_image({"image": "data"}) is False

    def test_integer_returns_false(self) -> None:
        """Test that integer returns False."""
        from backend.services.xclip_loader import _is_valid_pil_image

        assert _is_valid_pil_image(42) is False

    def test_different_pil_modes_return_true(self) -> None:
        """Test that different PIL modes are valid."""
        from backend.services.xclip_loader import _is_valid_pil_image

        # Test various PIL modes
        rgb_img = Image.new("RGB", (100, 100))
        assert _is_valid_pil_image(rgb_img) is True

        rgba_img = Image.new("RGBA", (100, 100))
        assert _is_valid_pil_image(rgba_img) is True

        l_img = Image.new("L", (100, 100))
        assert _is_valid_pil_image(l_img) is True

        p_img = Image.new("P", (100, 100))
        assert _is_valid_pil_image(p_img) is True

    def test_corrupted_pil_image_returns_false(self) -> None:
        """Test that corrupted PIL Image (can't access size/mode) returns False."""
        from backend.services.xclip_loader import _is_valid_pil_image

        # Create a mock that looks like PIL Image but raises on attribute access
        mock_img = MagicMock(spec=Image.Image)
        # Use PropertyMock to make size raise exception when accessed
        type(mock_img).size = PropertyMock(side_effect=OSError("Image corrupted"))

        assert _is_valid_pil_image(mock_img) is False


# =============================================================================
# Numpy Conversion Validation Tests
# =============================================================================


class TestNumpyConversionValidation:
    """Tests for _convert_to_numpy_safe and _validate_and_convert_frames functions."""

    def test_convert_to_numpy_safe_with_valid_image(self) -> None:
        """Test that valid PIL Image converts to numpy successfully."""
        from backend.services.xclip_loader import _convert_to_numpy_safe

        img = Image.new("RGB", (100, 100), color="red")
        arr = _convert_to_numpy_safe(img)

        assert arr is not None
        assert hasattr(arr, "shape")
        assert arr.shape == (100, 100, 3)

    def test_convert_to_numpy_safe_with_none(self) -> None:
        """Test that None input returns None (gracefully handles bad input)."""
        from backend.services.xclip_loader import _convert_to_numpy_safe

        # This would raise an exception without proper handling
        # but the function should catch it and return None
        try:
            result = _convert_to_numpy_safe(None)  # type: ignore[arg-type]
            # If it doesn't raise, it should return None
            assert result is None
        except (AttributeError, TypeError):
            # Also acceptable if it raises due to None.load()
            pass

    def test_convert_to_numpy_safe_with_grayscale(self) -> None:
        """Test numpy conversion with grayscale image."""
        from backend.services.xclip_loader import _convert_to_numpy_safe

        img = Image.new("L", (50, 50))
        arr = _convert_to_numpy_safe(img)

        assert arr is not None
        assert arr.shape == (50, 50)  # 2D for grayscale

    def test_convert_to_numpy_safe_with_rgba(self) -> None:
        """Test numpy conversion with RGBA image."""
        from backend.services.xclip_loader import _convert_to_numpy_safe

        img = Image.new("RGBA", (100, 100))
        arr = _convert_to_numpy_safe(img)

        assert arr is not None
        assert arr.shape == (100, 100, 4)  # 4 channels for RGBA

    def test_convert_to_numpy_safe_with_corrupted_image(self) -> None:
        """Test numpy conversion with corrupted image returns None."""
        from backend.services.xclip_loader import _convert_to_numpy_safe

        # Create a mock PIL Image that fails during load/array conversion
        mock_img = MagicMock(spec=Image.Image)
        mock_img.load.side_effect = OSError("Corrupted image data")

        result = _convert_to_numpy_safe(mock_img)
        assert result is None

    def test_convert_to_numpy_safe_returns_none_for_invalid_array(self) -> None:
        """Test that numpy conversion handles edge cases returning None."""
        from backend.services.xclip_loader import _convert_to_numpy_safe

        # Mock image that produces None array
        mock_img = MagicMock(spec=Image.Image)
        mock_img.load.return_value = None

        with patch("numpy.array", return_value=None):
            result = _convert_to_numpy_safe(mock_img)
            assert result is None

    def test_convert_to_numpy_safe_invalid_shape(self) -> None:
        """Test that arrays with invalid shapes are rejected."""
        from backend.services.xclip_loader import _convert_to_numpy_safe

        # Mock image that produces 1D array (invalid)
        mock_img = MagicMock(spec=Image.Image)
        mock_img.load.return_value = None

        with patch("numpy.array") as mock_array:
            invalid_arr = MagicMock()
            invalid_arr.shape = (100,)  # 1D, should be rejected
            mock_array.return_value = invalid_arr

            result = _convert_to_numpy_safe(mock_img)
            assert result is None

    def test_convert_to_numpy_safe_zero_dimensions(self) -> None:
        """Test that arrays with zero dimensions are rejected."""
        from backend.services.xclip_loader import _convert_to_numpy_safe

        # Mock image that produces array with zero dimensions
        mock_img = MagicMock(spec=Image.Image)
        mock_img.load.return_value = None

        with patch("numpy.array") as mock_array:
            invalid_arr = MagicMock()
            invalid_arr.shape = (0, 100, 3)  # Zero height
            mock_array.return_value = invalid_arr

            result = _convert_to_numpy_safe(mock_img)
            assert result is None

    def test_validate_and_convert_frames_filters_none(self) -> None:
        """Test that None frames are filtered out."""
        from backend.services.xclip_loader import _validate_and_convert_frames

        valid_img = Image.new("RGB", (100, 100))
        frames = [valid_img, None, valid_img]  # type: ignore[list-item]

        result = _validate_and_convert_frames(frames)  # type: ignore[arg-type]

        # Should only have the 2 valid images
        assert len(result) == 2

    def test_validate_and_convert_frames_logs_warning_for_corrupted(self) -> None:
        """Test that corrupted frames are logged and filtered."""
        from backend.services.xclip_loader import _validate_and_convert_frames

        # Create a valid image and a corrupted one
        valid_img = Image.new("RGB", (100, 100))

        # Mock corrupted image that passes PIL validation but fails numpy conversion
        mock_corrupted = MagicMock(spec=Image.Image)
        mock_corrupted.size = (100, 100)
        mock_corrupted.mode = "RGB"
        mock_corrupted.load.side_effect = OSError("Corrupted")

        frames = [valid_img, mock_corrupted, valid_img]  # type: ignore[list-item]

        result = _validate_and_convert_frames(frames)  # type: ignore[arg-type]

        # Should filter out the corrupted frame
        assert len(result) == 2

    def test_validate_and_convert_frames_filters_non_pil(self) -> None:
        """Test that non-PIL objects are filtered out."""
        from backend.services.xclip_loader import _validate_and_convert_frames

        valid_img = Image.new("RGB", (100, 100))
        frames = [valid_img, "string", {"dict": "object"}, 42, valid_img]  # type: ignore[list-item]

        result = _validate_and_convert_frames(frames)  # type: ignore[arg-type]

        # Should only have the 2 valid PIL images
        assert len(result) == 2

    def test_validate_and_convert_frames_all_valid(self) -> None:
        """Test that all valid frames are preserved."""
        from backend.services.xclip_loader import _validate_and_convert_frames

        frames = [Image.new("RGB", (100, 100)) for _ in range(5)]

        result = _validate_and_convert_frames(frames)

        assert len(result) == 5

    def test_validate_and_convert_frames_empty_list(self) -> None:
        """Test that empty list returns empty list."""
        from backend.services.xclip_loader import _validate_and_convert_frames

        result = _validate_and_convert_frames([])

        assert result == []

    def test_validate_and_convert_frames_all_invalid(self) -> None:
        """Test that all invalid frames returns empty list."""
        from backend.services.xclip_loader import _validate_and_convert_frames

        frames = [None, "string", 42]  # type: ignore[list-item]

        result = _validate_and_convert_frames(frames)  # type: ignore[arg-type]

        assert result == []


# =============================================================================
# Integration Tests for Null Frame Handling
# =============================================================================


class TestNullFrameHandlingIntegration:
    """Integration tests for null/invalid frame handling in classify_actions."""

    @pytest.mark.asyncio
    async def test_classify_actions_all_none_frames_raises_valueerror(self) -> None:
        """Test that passing all None frames raises ValueError."""
        from backend.services.xclip_loader import classify_actions

        model_dict = {"model": MagicMock(), "processor": MagicMock()}
        frames = [None, None, None]  # type: ignore[list-item]

        with pytest.raises(ValueError, match="No valid frames"):
            await classify_actions(model_dict, frames)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_classify_actions_mixed_none_and_valid_proceeds(self) -> None:
        """Test that mixed None and valid frames filters and proceeds."""
        from backend.services.xclip_loader import classify_actions

        # Create mock model and processor
        mock_model = MagicMock()
        mock_model.parameters.return_value = iter([MagicMock(device="cpu", dtype=MagicMock())])

        # Create a proper mock processor that returns valid tensors with correct shape
        mock_input_ids = MagicMock()
        mock_input_ids.to = MagicMock(return_value=mock_input_ids)
        mock_inputs = {
            "input_ids": mock_input_ids,
            "pixel_values": create_mock_pixel_values(),
        }

        mock_processor = MagicMock(return_value=mock_inputs)

        # Create mock outputs
        import torch

        mock_outputs = MagicMock()
        mock_outputs.logits_per_video = torch.tensor([[0.5, 0.3, 0.2]])

        mock_model.return_value = mock_outputs

        model_dict = {"model": mock_model, "processor": mock_processor}

        # Mix of None and valid frames
        valid_img = Image.new("RGB", (100, 100))
        frames = [None, valid_img, None, valid_img, None]  # type: ignore[list-item]

        # Should succeed with the valid frames (after filtering)
        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(
                return_value={
                    "detected_action": "walking",
                    "confidence": 0.5,
                    "top_actions": [("walking", 0.5)],
                    "all_scores": {"walking": 0.5},
                }
            )

            result = await classify_actions(model_dict, frames)  # type: ignore[arg-type]

        assert "detected_action" in result

    @pytest.mark.asyncio
    async def test_classify_actions_single_valid_frame_among_many_none(self) -> None:
        """Test that single valid frame among many None still works."""
        from backend.services.xclip_loader import classify_actions

        model_dict = {"model": MagicMock(), "processor": MagicMock()}
        valid_img = Image.new("RGB", (100, 100))

        # 9 None and 1 valid
        frames = [None] * 9 + [valid_img]  # type: ignore[list-item]

        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(
                return_value={
                    "detected_action": "standing",
                    "confidence": 0.8,
                    "top_actions": [("standing", 0.8)],
                    "all_scores": {"standing": 0.8},
                }
            )

            result = await classify_actions(model_dict, frames)  # type: ignore[arg-type]

        assert result["detected_action"] == "standing"

    @pytest.mark.asyncio
    async def test_classify_actions_string_in_frames_filtered(self) -> None:
        """Test that string objects in frames list are filtered out."""
        from backend.services.xclip_loader import classify_actions

        model_dict = {"model": MagicMock(), "processor": MagicMock()}
        valid_img = Image.new("RGB", (100, 100))

        # Mix valid images with strings (paths that weren't loaded)
        frames = [valid_img, "/path/to/image.jpg", valid_img]  # type: ignore[list-item]

        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(
                return_value={
                    "detected_action": "running",
                    "confidence": 0.7,
                    "top_actions": [("running", 0.7)],
                    "all_scores": {"running": 0.7},
                }
            )

            result = await classify_actions(model_dict, frames)  # type: ignore[arg-type]

        assert result["detected_action"] == "running"


# =============================================================================
# NEM-3506: Test pixel_values None Fix
# =============================================================================


class TestPixelValuesNoneFix:
    """Tests for NEM-3506 fix: X-CLIP processor returning None for pixel_values.

    The fix converts PIL Images to numpy arrays before passing to the processor
    to avoid lazy-loading issues that can cause pixel_values to be None.
    """

    @pytest.mark.asyncio
    async def test_frames_converted_to_numpy_arrays(self) -> None:
        """Test that frames are converted to numpy arrays before processor call."""
        mock_model = MagicMock()
        mock_processor = MagicMock()

        mock_param = MagicMock()
        mock_param.device = "cpu"
        mock_param.dtype = MagicMock()
        mock_model.parameters.return_value = iter([mock_param, mock_param])

        # Track what is passed to the processor
        captured_images: list[Any] = []

        def capture_processor_call(**kwargs: Any) -> dict[str, Any]:
            # NOTE: transformers 4.57+ uses `images=` param for video frames, not `videos=`
            captured_images.append(kwargs.get("images"))
            return {"pixel_values": create_mock_pixel_values()}

        mock_processor.side_effect = capture_processor_call

        mock_outputs = MagicMock()
        mock_probs = MagicMock()
        mock_probs.squeeze.return_value.cpu.return_value.numpy.return_value = np.array(
            [0.5, 0.3, 0.2]
        )
        mock_outputs.logits_per_video = MagicMock()
        mock_model.return_value = mock_outputs

        model_dict = {"model": mock_model, "processor": mock_processor}
        frames = [Image.new("RGB", (224, 224)) for _ in range(16)]

        mock_torch = MagicMock()
        mock_torch.no_grad.return_value.__enter__ = MagicMock(return_value=None)
        mock_torch.no_grad.return_value.__exit__ = MagicMock(return_value=None)
        mock_torch.softmax.return_value = mock_probs
        mock_torch.float16 = "float16"

        with patch.dict(sys.modules, {"torch": mock_torch}):
            await classify_actions(model_dict, frames, prompts=["a", "b", "c"])

        # Verify processor was called
        assert len(captured_images) == 1

        # The images argument should be a list of numpy arrays (video frames)
        images_arg = captured_images[0]
        assert isinstance(images_arg, list)
        assert len(images_arg) == 16  # 16 frames per NEM-3908

        # Each frame should be a numpy array, not a PIL Image
        for i, frame in enumerate(images_arg):
            assert isinstance(frame, np.ndarray), f"Frame {i} should be numpy array"
            assert frame.dtype == np.uint8, f"Frame {i} should have dtype uint8"
            assert len(frame.shape) == 3, f"Frame {i} should have 3 dimensions"
            assert frame.shape[2] == 3, f"Frame {i} should have 3 channels (RGB)"

    @pytest.mark.asyncio
    async def test_rgba_images_converted_to_rgb_numpy(self) -> None:
        """Test that RGBA images are properly converted to RGB numpy arrays."""
        mock_model = MagicMock()
        mock_processor = MagicMock()

        mock_param = MagicMock()
        mock_param.device = "cpu"
        mock_param.dtype = MagicMock()
        mock_model.parameters.return_value = iter([mock_param, mock_param])

        captured_images: list[Any] = []

        def capture_processor_call(**kwargs: Any) -> dict[str, Any]:
            # NOTE: transformers 4.57+ uses `images=` param for video frames, not `videos=`
            captured_images.append(kwargs.get("images"))
            return {"pixel_values": create_mock_pixel_values()}

        mock_processor.side_effect = capture_processor_call

        mock_outputs = MagicMock()
        mock_probs = MagicMock()
        mock_probs.squeeze.return_value.cpu.return_value.numpy.return_value = np.array(
            [0.5, 0.3, 0.2]
        )
        mock_outputs.logits_per_video = MagicMock()
        mock_model.return_value = mock_outputs

        model_dict = {"model": mock_model, "processor": mock_processor}

        # Create RGBA images (4 channels) - 16 frames per NEM-3908
        frames = [Image.new("RGBA", (224, 224), color=(255, 0, 0, 128)) for _ in range(16)]

        mock_torch = MagicMock()
        mock_torch.no_grad.return_value.__enter__ = MagicMock(return_value=None)
        mock_torch.no_grad.return_value.__exit__ = MagicMock(return_value=None)
        mock_torch.softmax.return_value = mock_probs
        mock_torch.float16 = "float16"

        with patch.dict(sys.modules, {"torch": mock_torch}):
            await classify_actions(model_dict, frames, prompts=["a", "b", "c"])

        # Verify frames were converted to RGB (3 channels)
        images_arg = captured_images[0]

        for i, frame in enumerate(images_arg):
            assert isinstance(frame, np.ndarray), f"Frame {i} should be numpy array"
            assert frame.shape[2] == 3, f"Frame {i} should have 3 channels (converted from RGBA)"

    @pytest.mark.asyncio
    async def test_grayscale_images_converted_to_rgb_numpy(self) -> None:
        """Test that grayscale images are properly converted to RGB numpy arrays."""
        mock_model = MagicMock()
        mock_processor = MagicMock()

        mock_param = MagicMock()
        mock_param.device = "cpu"
        mock_param.dtype = MagicMock()
        mock_model.parameters.return_value = iter([mock_param, mock_param])

        captured_images: list[Any] = []

        def capture_processor_call(**kwargs: Any) -> dict[str, Any]:
            # NOTE: transformers 4.57+ uses `images=` param for video frames, not `videos=`
            captured_images.append(kwargs.get("images"))
            return {"pixel_values": create_mock_pixel_values()}

        mock_processor.side_effect = capture_processor_call

        mock_outputs = MagicMock()
        mock_probs = MagicMock()
        mock_probs.squeeze.return_value.cpu.return_value.numpy.return_value = np.array(
            [0.5, 0.3, 0.2]
        )
        mock_outputs.logits_per_video = MagicMock()
        mock_model.return_value = mock_outputs

        model_dict = {"model": mock_model, "processor": mock_processor}

        # Create grayscale images (mode "L") - 16 frames per NEM-3908
        frames = [Image.new("L", (224, 224)) for _ in range(16)]

        mock_torch = MagicMock()
        mock_torch.no_grad.return_value.__enter__ = MagicMock(return_value=None)
        mock_torch.no_grad.return_value.__exit__ = MagicMock(return_value=None)
        mock_torch.softmax.return_value = mock_probs
        mock_torch.float16 = "float16"

        with patch.dict(sys.modules, {"torch": mock_torch}):
            await classify_actions(model_dict, frames, prompts=["a", "b", "c"])

        # Verify frames were converted to RGB (3 channels)
        images_arg = captured_images[0]

        for i, frame in enumerate(images_arg):
            assert isinstance(frame, np.ndarray), f"Frame {i} should be numpy array"
            assert len(frame.shape) == 3, f"Frame {i} should have 3 dimensions"
            assert frame.shape[2] == 3, f"Frame {i} should have 3 channels (converted from L)"


# =============================================================================
# Hierarchical Security Action Categories Tests (NEM-3913)
# =============================================================================


class TestActionPromptsV2Structure:
    """Tests for ACTION_PROMPTS_V2 hierarchical structure."""

    def test_action_prompts_v2_exists(self) -> None:
        """Test ACTION_PROMPTS_V2 is defined."""
        assert ACTION_PROMPTS_V2 is not None
        assert isinstance(ACTION_PROMPTS_V2, dict)

    def test_action_prompts_v2_has_expected_categories(self) -> None:
        """Test ACTION_PROMPTS_V2 has expected category keys."""
        expected_categories = {
            "high_risk",
            "suspicious",
            "approaching",
            "delivery",
            "normal",
            "stationary",
            "fleeing",
        }
        assert set(ACTION_PROMPTS_V2.keys()) == expected_categories

    def test_each_category_has_required_fields(self) -> None:
        """Test each category has prompts and threshold."""
        for category, config in ACTION_PROMPTS_V2.items():
            assert "prompts" in config, f"Category {category} missing prompts"
            assert "threshold" in config, f"Category {category} missing threshold"
            assert isinstance(config["prompts"], list)
            assert isinstance(config["threshold"], float)

    def test_high_risk_category_has_lowest_threshold(self) -> None:
        """Test high_risk category has lowest threshold (don't miss threats)."""
        high_risk_threshold = ACTION_PROMPTS_V2["high_risk"]["threshold"]
        for category, config in ACTION_PROMPTS_V2.items():
            if category != "high_risk":
                assert config["threshold"] >= high_risk_threshold

    def test_total_prompt_count_increased(self) -> None:
        """Test total prompts expanded to 25+ as per requirement."""
        total = sum(len(config["prompts"]) for config in ACTION_PROMPTS_V2.values())
        assert total >= 25, f"Expected at least 25 prompts, got {total}"


class TestGetAllActionPrompts:
    """Tests for get_all_action_prompts function."""

    def test_returns_list(self) -> None:
        """Test function returns a list."""
        result = get_all_action_prompts()
        assert isinstance(result, list)

    def test_returns_all_prompts(self) -> None:
        """Test function returns prompts from all categories."""
        result = get_all_action_prompts()
        expected_count = sum(len(config["prompts"]) for config in ACTION_PROMPTS_V2.values())
        assert len(result) == expected_count

    def test_contains_high_risk_prompts(self) -> None:
        """Test result contains high risk prompts."""
        result = get_all_action_prompts()
        assert "a person breaking in" in result

    def test_contains_delivery_prompts(self) -> None:
        """Test result contains delivery prompts."""
        result = get_all_action_prompts()
        assert "a delivery driver carrying a package to a door" in result

    def test_matches_legacy_constant(self) -> None:
        """Test get_all_action_prompts matches SECURITY_ACTION_PROMPTS."""
        result = get_all_action_prompts()
        assert result == SECURITY_ACTION_PROMPTS


class TestGetActionRiskLevel:
    """Tests for get_action_risk_level function."""

    def test_high_risk_prompts_return_critical(self) -> None:
        """Test high risk prompts return critical risk level."""
        assert get_action_risk_level("a person breaking in") == "critical"
        assert get_action_risk_level("a person vandalizing property") == "critical"

    def test_suspicious_prompts_return_high(self) -> None:
        """Test suspicious prompts return high risk level."""
        assert get_action_risk_level("a person loitering") == "high"
        assert get_action_risk_level("a person hiding near bushes") == "high"

    def test_fleeing_prompts_return_high(self) -> None:
        """Test fleeing prompts return high risk level."""
        assert get_action_risk_level("a person running away from a location") == "high"

    def test_approaching_prompts_return_medium(self) -> None:
        """Test approaching prompts return medium risk level."""
        assert get_action_risk_level("a person approaching a front door") == "medium"
        assert get_action_risk_level("a person approaching a door") == "medium"

    def test_delivery_prompts_return_low(self) -> None:
        """Test delivery prompts return low risk level."""
        assert get_action_risk_level("a delivery driver carrying a package to a door") == "low"
        assert get_action_risk_level("a person delivering a package") == "low"

    def test_normal_prompts_return_low(self) -> None:
        """Test normal prompts return low risk level."""
        assert get_action_risk_level("a person walking normally") == "low"
        assert get_action_risk_level("a person knocking on door") == "low"

    def test_unknown_prompt_returns_low(self) -> None:
        """Test unknown prompts return low risk level as default."""
        assert get_action_risk_level("unknown action prompt") == "low"


class TestGetActionThreshold:
    """Tests for get_action_threshold function."""

    def test_high_risk_threshold(self) -> None:
        """Test high_risk category has 0.20 threshold."""
        assert get_action_threshold("high_risk") == 0.20

    def test_suspicious_threshold(self) -> None:
        """Test suspicious category has 0.25 threshold."""
        assert get_action_threshold("suspicious") == 0.25

    def test_approaching_threshold(self) -> None:
        """Test approaching category has 0.30 threshold."""
        assert get_action_threshold("approaching") == 0.30

    def test_delivery_threshold(self) -> None:
        """Test delivery category has 0.35 threshold."""
        assert get_action_threshold("delivery") == 0.35

    def test_normal_threshold(self) -> None:
        """Test normal category has 0.40 threshold."""
        assert get_action_threshold("normal") == 0.40

    def test_unknown_category_returns_default(self) -> None:
        """Test unknown category returns 0.35 as default."""
        assert get_action_threshold("nonexistent_category") == 0.35


class TestGetActionCategory:
    """Tests for get_action_category function."""

    def test_high_risk_prompts_return_high_risk(self) -> None:
        """Test high risk prompts return high_risk category."""
        assert get_action_category("a person breaking in") == "high_risk"
        assert get_action_category("a person vandalizing property") == "high_risk"

    def test_suspicious_prompts_return_suspicious(self) -> None:
        """Test suspicious prompts return suspicious category."""
        assert get_action_category("a person loitering") == "suspicious"

    def test_approaching_prompts_return_approaching(self) -> None:
        """Test approaching prompts return approaching category."""
        assert get_action_category("a person approaching a door") == "approaching"

    def test_delivery_prompts_return_delivery(self) -> None:
        """Test delivery prompts return delivery category."""
        assert get_action_category("a person delivering a package") == "delivery"

    def test_normal_prompts_return_normal(self) -> None:
        """Test normal prompts return normal category."""
        assert get_action_category("a person walking normally") == "normal"

    def test_fleeing_prompts_return_fleeing(self) -> None:
        """Test fleeing prompts return fleeing category."""
        assert get_action_category("a person running away") == "fleeing"

    def test_unknown_prompt_returns_none(self) -> None:
        """Test unknown prompts return None."""
        assert get_action_category("unknown action prompt") is None


class TestActionBackwardCompatibility:
    """Tests for backward compatibility with legacy constants."""

    def test_security_action_prompts_not_empty(self) -> None:
        """Test SECURITY_ACTION_PROMPTS is not empty."""
        assert len(SECURITY_ACTION_PROMPTS) > 0

    def test_security_action_prompts_contains_legacy_prompts(self) -> None:
        """Test SECURITY_ACTION_PROMPTS contains legacy prompts."""
        # These were in the original constant
        assert "a person loitering" in SECURITY_ACTION_PROMPTS
        assert "a person approaching a door" in SECURITY_ACTION_PROMPTS
        assert "a person breaking in" in SECURITY_ACTION_PROMPTS
        assert "a person delivering a package" in SECURITY_ACTION_PROMPTS

    def test_most_prompts_describe_person_action(self) -> None:
        """Test most prompts describe a person's action.

        Note: Some prompts may refer to specific roles (e.g., 'delivery driver')
        instead of 'person', which is acceptable for better classification.
        """
        person_count = sum(1 for p in SECURITY_ACTION_PROMPTS if "person" in p.lower())
        total_count = len(SECURITY_ACTION_PROMPTS)
        # At least 70% should mention 'person' to maintain semantic consistency
        assert person_count >= total_count * 0.7, (
            f"Only {person_count}/{total_count} prompts mention 'person'"
        )
