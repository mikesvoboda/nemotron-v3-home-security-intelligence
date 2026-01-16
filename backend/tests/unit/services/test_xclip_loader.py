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
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PIL import Image

from backend.services.xclip_loader import (
    SECURITY_ACTION_PROMPTS,
    classify_actions,
    get_action_risk_weight,
    is_suspicious_action,
    load_xclip_model,
    sample_frames_from_batch,
)

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
            result = await load_xclip_model("microsoft/xclip-base-patch32")

        assert "model" in result
        assert "processor" in result
        mock_xclip_processor_cls.from_pretrained.assert_called_once_with(
            "microsoft/xclip-base-patch32"
        )


# =============================================================================
# classify_actions Tests
# =============================================================================


class TestClassifyActions:
    """Tests for classify_actions function."""

    @pytest.fixture
    def sample_frames(self) -> list[Image.Image]:
        """Create sample PIL Image frames for testing."""
        return [Image.new("RGB", (224, 224), color="red") for _ in range(8)]

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

        mock_inputs = {"pixel_values": MagicMock()}
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

        # Set up processor return value
        mock_inputs = {"pixel_values": MagicMock(), "input_ids": MagicMock()}
        for v in mock_inputs.values():
            v.to.return_value = v
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

        mock_inputs = {"pixel_values": MagicMock(), "input_ids": MagicMock()}
        for v in mock_inputs.values():
            v.to.return_value = v
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
    async def test_classify_with_fewer_than_8_frames(self) -> None:
        """Test classification with fewer than 8 frames (should duplicate)."""
        frames = [Image.new("RGB", (224, 224), color="blue") for _ in range(3)]

        mock_model = MagicMock()
        mock_processor = MagicMock()

        mock_param = MagicMock()
        mock_param.device = "cpu"
        mock_param.dtype = MagicMock()
        mock_model.parameters.return_value = iter([mock_param, mock_param])

        mock_inputs = {"pixel_values": MagicMock()}
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
    async def test_classify_with_more_than_8_frames(self) -> None:
        """Test classification with more than 8 frames (should sample)."""
        frames = [Image.new("RGB", (224, 224), color="green") for _ in range(16)]

        mock_model = MagicMock()
        mock_processor = MagicMock()

        mock_param = MagicMock()
        mock_param.device = "cpu"
        mock_param.dtype = MagicMock()
        mock_model.parameters.return_value = iter([mock_param, mock_param])

        mock_inputs = {"pixel_values": MagicMock()}
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
    async def test_classify_with_exactly_8_frames(self, sample_frames: list[Image.Image]) -> None:
        """Test classification with exactly 8 frames."""
        assert len(sample_frames) == 8

        mock_model = MagicMock()
        mock_processor = MagicMock()

        mock_param = MagicMock()
        mock_param.device = "cpu"
        mock_param.dtype = MagicMock()
        mock_model.parameters.return_value = iter([mock_param, mock_param])

        mock_inputs = {"pixel_values": MagicMock()}
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

        mock_inputs = {"pixel_values": MagicMock()}
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

        # Set up processor
        mock_pixel_values = MagicMock()
        mock_pixel_values.to.return_value = mock_pixel_values
        mock_pixel_values.half.return_value = mock_pixel_values
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
        # Verify float16 conversion was called
        mock_pixel_values.half.assert_called()


# =============================================================================
# sample_frames_from_batch Tests
# =============================================================================


class TestSampleFramesFromBatch:
    """Tests for sample_frames_from_batch function."""

    def test_sample_fewer_frames_returns_all(self) -> None:
        """Test that fewer frames than target returns all frames."""
        frame_paths = ["/path/frame1.jpg", "/path/frame2.jpg", "/path/frame3.jpg"]
        result = sample_frames_from_batch(frame_paths, target_count=8)
        assert result == frame_paths

    def test_sample_exact_frames_returns_all(self) -> None:
        """Test that exact number of frames returns all frames."""
        frame_paths = [f"/path/frame{i}.jpg" for i in range(8)]
        result = sample_frames_from_batch(frame_paths, target_count=8)
        assert result == frame_paths

    def test_sample_more_frames_uniform_sampling(self) -> None:
        """Test that more frames are uniformly sampled."""
        frame_paths = [f"/path/frame{i}.jpg" for i in range(16)]
        result = sample_frames_from_batch(frame_paths, target_count=8)

        assert len(result) == 8
        # Should include first frame
        assert result[0] == "/path/frame0.jpg"
        # Should have frames distributed across the range
        assert "/path/frame8.jpg" in result or "/path/frame7.jpg" in result

    def test_sample_default_target_count(self) -> None:
        """Test default target_count of 8."""
        frame_paths = [f"/path/frame{i}.jpg" for i in range(20)]
        result = sample_frames_from_batch(frame_paths)
        assert len(result) == 8

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
        mock_inputs = {"pixel_values": MagicMock()}
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

        # Sample for X-CLIP processing
        sampled = sample_frames_from_batch(batch_paths, target_count=8)

        assert len(sampled) == 8
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

    @pytest.mark.asyncio
    async def test_classify_single_frame(self) -> None:
        """Test classification with single frame (should pad to 8)."""
        mock_model = MagicMock()
        mock_processor = MagicMock()

        mock_param = MagicMock()
        mock_param.device = "cpu"
        mock_param.dtype = MagicMock()
        mock_model.parameters.return_value = iter([mock_param, mock_param])

        mock_inputs = {"pixel_values": MagicMock()}
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
        """Test that all security prompts are unique."""
        assert len(SECURITY_ACTION_PROMPTS) == len(set(SECURITY_ACTION_PROMPTS))

    def test_security_prompts_start_with_person(self) -> None:
        """Test that all security prompts describe a person's action."""
        for prompt in SECURITY_ACTION_PROMPTS:
            assert "person" in prompt.lower()
