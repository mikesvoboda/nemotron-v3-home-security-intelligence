"""Unit tests for ActionRecognizer X-CLIP video action recognition.

These tests validate the ActionRecognizer implementation including:
- Frame sampling from video sequences
- Suspicious action flagging
- ActionResult dataclass
- Model loading/unloading
- Error handling

Tests use mocked models to avoid requiring GPU or actual model files.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PIL import Image

from ai.enrichment.models.action_recognizer import (
    SECURITY_ACTIONS,
    SUSPICIOUS_ACTIONS,
    ActionRecognizer,
    ActionResult,
    load_action_recognizer,
)


class TestActionResult:
    """Tests for the ActionResult dataclass."""

    def test_action_result_creation(self) -> None:
        """Test creating an ActionResult with all fields."""
        result = ActionResult(
            action="walking normally",
            confidence=0.85,
            is_suspicious=False,
            all_scores={"walking normally": 0.85, "running": 0.10, "climbing": 0.05},
        )

        assert result.action == "walking normally"
        assert result.confidence == 0.85
        assert result.is_suspicious is False
        assert len(result.all_scores) == 3

    def test_action_result_suspicious(self) -> None:
        """Test ActionResult with suspicious action."""
        result = ActionResult(
            action="climbing",
            confidence=0.72,
            is_suspicious=True,
            all_scores={"climbing": 0.72, "walking normally": 0.18},
        )

        assert result.action == "climbing"
        assert result.is_suspicious is True


class TestSecurityActions:
    """Tests for security action definitions."""

    def test_security_actions_count(self) -> None:
        """Test that we have 15 security-relevant action classes."""
        assert len(SECURITY_ACTIONS) == 15

    def test_security_actions_content(self) -> None:
        """Test that expected actions are in the list."""
        expected_normal = ["walking normally", "running", "delivering package"]
        expected_suspicious = ["climbing", "breaking window", "picking lock"]

        for action in expected_normal:
            assert action in SECURITY_ACTIONS

        for action in expected_suspicious:
            assert action in SECURITY_ACTIONS

    def test_suspicious_actions_is_subset(self) -> None:
        """Test that suspicious actions are a subset of security actions."""
        for action in SUSPICIOUS_ACTIONS:
            assert action in SECURITY_ACTIONS

    def test_suspicious_actions_count(self) -> None:
        """Test that we have 7 suspicious action classes."""
        assert len(SUSPICIOUS_ACTIONS) == 7

    def test_suspicious_actions_content(self) -> None:
        """Test that expected suspicious actions are flagged."""
        expected_suspicious = {
            "fighting",
            "climbing",
            "breaking window",
            "picking lock",
            "hiding",
            "loitering",
            "looking around suspiciously",
        }

        assert expected_suspicious == SUSPICIOUS_ACTIONS


class TestActionRecognizerFrameSampling:
    """Tests for frame sampling logic."""

    @pytest.fixture
    def recognizer(self) -> ActionRecognizer:
        """Create an ActionRecognizer without loading the model."""
        return ActionRecognizer(model_path="microsoft/xclip-base-patch16-16-frames")

    def test_sample_frames_exact_count(self, recognizer: ActionRecognizer) -> None:
        """Test sampling when input has exactly required number of frames."""
        frames = [Image.new("RGB", (224, 224)) for _ in range(8)]
        sampled = recognizer._sample_frames(frames, num_frames=8)

        assert len(sampled) == 8
        # All frames should be PIL Images
        assert all(isinstance(f, Image.Image) for f in sampled)

    def test_sample_frames_more_than_needed(self, recognizer: ActionRecognizer) -> None:
        """Test sampling when input has more frames than needed."""
        frames = [Image.new("RGB", (224, 224), color=(i * 10, 0, 0)) for i in range(24)]
        sampled = recognizer._sample_frames(frames, num_frames=8)

        assert len(sampled) == 8
        # Should sample evenly from the sequence
        assert all(isinstance(f, Image.Image) for f in sampled)

    def test_sample_frames_fewer_than_needed(self, recognizer: ActionRecognizer) -> None:
        """Test sampling when input has fewer frames than needed (padding)."""
        frames = [Image.new("RGB", (224, 224)) for _ in range(3)]
        sampled = recognizer._sample_frames(frames, num_frames=8)

        assert len(sampled) == 8
        # Last frame should be repeated for padding
        assert all(isinstance(f, Image.Image) for f in sampled)

    def test_sample_frames_single_frame(self, recognizer: ActionRecognizer) -> None:
        """Test sampling with a single input frame."""
        frames = [Image.new("RGB", (224, 224), color=(100, 100, 100))]
        sampled = recognizer._sample_frames(frames, num_frames=8)

        assert len(sampled) == 8
        # All frames should be the same (repeated)
        for frame in sampled:
            assert isinstance(frame, Image.Image)

    def test_sample_frames_empty_raises(self, recognizer: ActionRecognizer) -> None:
        """Test that empty frame list raises ValueError."""
        with pytest.raises(ValueError, match="Cannot sample from empty frame list"):
            recognizer._sample_frames([], num_frames=8)

    def test_sample_frames_numpy_conversion(self, recognizer: ActionRecognizer) -> None:
        """Test that numpy arrays are converted to PIL Images."""
        numpy_frames = [np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8) for _ in range(4)]
        sampled = recognizer._sample_frames(numpy_frames, num_frames=8)

        assert len(sampled) == 8
        assert all(isinstance(f, Image.Image) for f in sampled)
        assert all(f.mode == "RGB" for f in sampled)

    def test_sample_frames_grayscale_numpy(self, recognizer: ActionRecognizer) -> None:
        """Test that grayscale numpy arrays are converted to RGB."""
        grayscale_frames = [np.random.randint(0, 255, (224, 224), dtype=np.uint8) for _ in range(4)]
        sampled = recognizer._sample_frames(grayscale_frames, num_frames=8)

        assert len(sampled) == 8
        assert all(isinstance(f, Image.Image) for f in sampled)
        assert all(f.mode == "RGB" for f in sampled)

    def test_sample_frames_rgba_numpy(self, recognizer: ActionRecognizer) -> None:
        """Test that RGBA numpy arrays are converted to RGB."""
        rgba_frames = [np.random.randint(0, 255, (224, 224, 4), dtype=np.uint8) for _ in range(4)]
        sampled = recognizer._sample_frames(rgba_frames, num_frames=8)

        assert len(sampled) == 8
        assert all(isinstance(f, Image.Image) for f in sampled)
        assert all(f.mode == "RGB" for f in sampled)

    def test_sample_frames_non_rgb_pil(self, recognizer: ActionRecognizer) -> None:
        """Test that non-RGB PIL Images are converted to RGB."""
        la_frames = [Image.new("LA", (224, 224)) for _ in range(4)]  # Grayscale with alpha
        sampled = recognizer._sample_frames(la_frames, num_frames=8)

        assert len(sampled) == 8
        assert all(isinstance(f, Image.Image) for f in sampled)
        assert all(f.mode == "RGB" for f in sampled)


class TestActionRecognizerModelLoading:
    """Tests for model loading and unloading."""

    def test_init_stores_path_and_device(self) -> None:
        """Test that initialization stores model path and device."""
        recognizer = ActionRecognizer(
            model_path="/models/xclip",
            device="cuda:0",
        )

        assert recognizer.model_path == "/models/xclip"
        assert recognizer.device == "cuda:0"
        assert recognizer.model is None
        assert recognizer.processor is None
        assert recognizer.num_frames == 16  # NEM-3908: upgraded to 16 frames

    def test_recognize_action_without_load_raises(self) -> None:
        """Test that calling recognize_action before load_model raises."""
        recognizer = ActionRecognizer(model_path="/models/xclip")
        frames = [Image.new("RGB", (224, 224)) for _ in range(4)]

        with pytest.raises(RuntimeError, match="Model not loaded"):
            recognizer.recognize_action(frames)

    def test_recognize_action_empty_frames_raises(self) -> None:
        """Test that empty frames list raises ValueError."""
        recognizer = ActionRecognizer(model_path="/models/xclip")
        # Mock model as loaded
        recognizer.model = MagicMock()
        recognizer.processor = MagicMock()

        with pytest.raises(ValueError, match="Frames list cannot be empty"):
            recognizer.recognize_action([])

    def test_unload_model_clears_references(self) -> None:
        """Test that unload_model clears model references."""
        recognizer = ActionRecognizer(model_path="/models/xclip", device="cpu")
        recognizer.model = MagicMock()
        recognizer.processor = MagicMock()

        recognizer.unload_model()

        assert recognizer.model is None
        assert recognizer.processor is None


class TestActionRecognizerInference:
    """Tests for action recognition inference with mocked model."""

    @pytest.fixture
    def mock_recognizer(self) -> ActionRecognizer:
        """Create a recognizer with mocked model and processor."""
        recognizer = ActionRecognizer(model_path="/models/xclip", device="cpu")

        # Mock the processor
        mock_processor = MagicMock()
        mock_processor.return_value = {
            "pixel_values": MagicMock(),
            "input_ids": MagicMock(),
        }
        recognizer.processor = mock_processor

        # Mock the model
        mock_model = MagicMock()
        # Create mock outputs with logits
        mock_outputs = MagicMock()
        # Logits shape: (1, num_actions) - one video, all actions
        # Simulate higher score for "walking normally" (index 0)
        import torch

        logits = torch.zeros(1, len(SECURITY_ACTIONS))
        logits[0, 0] = 2.0  # "walking normally" has highest logit
        logits[0, 1] = 1.0  # "running" second highest
        mock_outputs.logits_per_video = logits
        mock_model.return_value = mock_outputs
        recognizer.model = mock_model

        return recognizer

    def test_recognize_action_normal_activity(
        self,
        mock_recognizer: ActionRecognizer,
    ) -> None:
        """Test recognition of normal activity."""
        frames = [Image.new("RGB", (224, 224)) for _ in range(8)]

        result = mock_recognizer.recognize_action(frames)

        assert isinstance(result, ActionResult)
        assert result.action == "walking normally"
        assert result.confidence > 0
        assert result.is_suspicious is False
        assert len(result.all_scores) == len(SECURITY_ACTIONS)

    def test_recognize_action_with_custom_actions(
        self,
        mock_recognizer: ActionRecognizer,
    ) -> None:
        """Test recognition with custom action list."""
        import torch

        # Update mock for custom actions
        custom_actions = ["sitting", "standing", "waving"]
        mock_outputs = MagicMock()
        logits = torch.zeros(1, len(custom_actions))
        logits[0, 2] = 1.5  # "waving" highest
        mock_outputs.logits_per_video = logits
        mock_recognizer.model.return_value = mock_outputs

        frames = [Image.new("RGB", (224, 224)) for _ in range(8)]
        result = mock_recognizer.recognize_action(frames, actions=custom_actions)

        assert result.action == "waving"
        assert len(result.all_scores) == 3

    def test_recognize_suspicious_action(self) -> None:
        """Test that suspicious actions are flagged."""
        import torch

        recognizer = ActionRecognizer(model_path="/models/xclip", device="cpu")
        recognizer.processor = MagicMock(
            return_value={
                "pixel_values": MagicMock(),
                "input_ids": MagicMock(),
            }
        )

        # Mock model to return "climbing" as top action
        mock_outputs = MagicMock()
        logits = torch.zeros(1, len(SECURITY_ACTIONS))
        # Find index of "climbing"
        climbing_idx = SECURITY_ACTIONS.index("climbing")
        logits[0, climbing_idx] = 3.0  # High score for climbing
        mock_outputs.logits_per_video = logits
        mock_model = MagicMock(return_value=mock_outputs)
        recognizer.model = mock_model

        frames = [Image.new("RGB", (224, 224)) for _ in range(8)]
        result = recognizer.recognize_action(frames)

        assert result.action == "climbing"
        assert result.is_suspicious is True


class TestActionRecognizerBatchInference:
    """Tests for batch action recognition."""

    def test_recognize_action_batch_empty_raises(self) -> None:
        """Test that empty batch raises ValueError."""
        recognizer = ActionRecognizer(model_path="/models/xclip")
        recognizer.model = MagicMock()
        recognizer.processor = MagicMock()

        with pytest.raises(ValueError, match="Frame sequences list cannot be empty"):
            recognizer.recognize_action_batch([])

    def test_recognize_action_batch_empty_sequence_raises(self) -> None:
        """Test that empty sequence in batch raises ValueError."""
        recognizer = ActionRecognizer(model_path="/models/xclip")
        recognizer.model = MagicMock()
        recognizer.processor = MagicMock()

        with pytest.raises(ValueError, match="Frame sequence cannot be empty"):
            recognizer.recognize_action_batch([[]])

    def test_recognize_action_batch_without_load_raises(self) -> None:
        """Test that batch inference without loading raises."""
        recognizer = ActionRecognizer(model_path="/models/xclip")
        sequences = [[Image.new("RGB", (224, 224)) for _ in range(4)]]

        with pytest.raises(RuntimeError, match="Model not loaded"):
            recognizer.recognize_action_batch(sequences)


class TestLoadActionRecognizer:
    """Tests for the factory function."""

    @patch.object(ActionRecognizer, "load_model")
    def test_load_action_recognizer_creates_and_loads(
        self,
        mock_load: MagicMock,
    ) -> None:
        """Test that factory function creates and loads recognizer."""
        mock_load.return_value = MagicMock()

        recognizer = load_action_recognizer(
            model_path="/models/xclip",
            device="cpu",
        )

        assert isinstance(recognizer, ActionRecognizer)
        assert recognizer.model_path == "/models/xclip"
        assert recognizer.device == "cpu"
        mock_load.assert_called_once()


class TestSuspiciousActionFlagging:
    """Tests for correct suspicious action identification."""

    @pytest.mark.parametrize("action", list(SUSPICIOUS_ACTIONS))
    def test_suspicious_actions_are_flagged(self, action: str) -> None:
        """Test that all suspicious actions are correctly flagged."""
        result = ActionResult(
            action=action,
            confidence=0.8,
            is_suspicious=action in SUSPICIOUS_ACTIONS,
            all_scores={action: 0.8},
        )

        assert result.is_suspicious is True

    @pytest.mark.parametrize(
        "action",
        [a for a in SECURITY_ACTIONS if a not in SUSPICIOUS_ACTIONS],
    )
    def test_normal_actions_not_flagged(self, action: str) -> None:
        """Test that normal actions are not flagged as suspicious."""
        result = ActionResult(
            action=action,
            confidence=0.8,
            is_suspicious=action in SUSPICIOUS_ACTIONS,
            all_scores={action: 0.8},
        )

        assert result.is_suspicious is False
