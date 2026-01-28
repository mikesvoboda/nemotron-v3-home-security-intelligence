"""X-CLIP Video Action Recognition Module.

This module provides the ActionRecognizer class for video-based action recognition
using Microsoft's X-CLIP model. It analyzes sequences of frames to understand
what people are doing over time.

Model Details (NEM-3908 upgrade):
- Model: microsoft/xclip-base-patch16-16-frames
- VRAM: ~2GB
- Priority: LOW (expensive, use sparingly)
- Input: 16 frames (optimal), supports 8-32 frames
- Output: Action classification with confidence
- Accuracy: +4% improvement over patch32 8-frame variant

Trigger Conditions (document for model orchestration):
- Only run action recognition when:
  - Person detected for >3 seconds
  - Multiple frames available in buffer
  - Unusual pose detected (trigger from pose estimator)

Reference: https://huggingface.co/microsoft/xclip-base-patch16-16-frames
Design Doc: docs/plans/2026-01-19-model-zoo-prompt-improvements-design.md Section 5.5
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
import torch
from PIL import Image

if TYPE_CHECKING:
    from transformers import XCLIPModel, XCLIPProcessor

logger = logging.getLogger(__name__)


@dataclass
class ActionResult:
    """Result from action recognition inference.

    Attributes:
        action: The recognized action (e.g., "walking normally", "climbing")
        confidence: Confidence score for the recognized action (0.0 to 1.0)
        is_suspicious: Whether the action is flagged as security-relevant
        all_scores: Dictionary mapping all action classes to their scores
    """

    action: str
    confidence: float
    is_suspicious: bool
    all_scores: dict[str, float]


# Security-relevant action classes for home surveillance scenarios
# These cover normal activities, potentially suspicious behaviors, and emergency situations
SECURITY_ACTIONS: list[str] = [
    # Normal activities
    "walking normally",
    "running",
    "delivering package",
    "checking mailbox",
    "ringing doorbell",
    "waving",
    # Potentially suspicious activities
    "fighting",
    "falling down",
    "climbing",
    "breaking window",
    "picking lock",
    "hiding",
    "loitering",
    "carrying large object",
    "looking around suspiciously",
]

# Actions that should flag security alerts
SUSPICIOUS_ACTIONS: frozenset[str] = frozenset(
    {
        "fighting",
        "climbing",
        "breaking window",
        "picking lock",
        "hiding",
        "loitering",
        "looking around suspiciously",
    }
)


class ActionRecognizer:
    """X-CLIP video action recognition model wrapper.

    Uses Microsoft's X-CLIP model for zero-shot video action classification.
    The model analyzes sequences of frames to understand temporal patterns
    and classify activities.

    Model: microsoft/xclip-base-patch16-16-frames (NEM-3908)
    VRAM Usage: ~2GB
    Typical Inference Time: ~300-600ms for 16 frames

    Example usage:
        recognizer = ActionRecognizer("/models/xclip-base-patch16-16-frames")
        recognizer.load_model()

        # Get frames from video buffer (list of PIL Images or numpy arrays)
        frames = [frame1, frame2, frame3, ...]

        result = recognizer.recognize_action(frames)
        print(f"Action: {result.action} (confidence: {result.confidence:.2%})")
        if result.is_suspicious:
            print("ALERT: Suspicious activity detected!")
    """

    def __init__(self, model_path: str, device: str = "cuda:0"):
        """Initialize action recognizer.

        Args:
            model_path: Path to X-CLIP model directory or HuggingFace model ID
                       (e.g., "microsoft/xclip-base-patch16-16-frames" or
                       "/models/xclip-base-patch16-16-frames")
            device: Device to run inference on (e.g., "cuda:0" or "cpu")
        """
        self.model_path = model_path
        self.device = device
        self.model: XCLIPModel | None = None
        self.processor: XCLIPProcessor | None = None
        self.num_frames = 16  # X-CLIP patch16-16-frames uses 16 frames (NEM-3908)

        logger.info(f"Initializing ActionRecognizer from {self.model_path}")

    def load_model(self) -> ActionRecognizer:
        """Load the X-CLIP model into memory.

        Returns:
            Self for method chaining.

        Raises:
            ImportError: If transformers library is not available.
            OSError: If model files cannot be loaded.
        """
        from transformers import XCLIPModel, XCLIPProcessor

        logger.info("Loading X-CLIP model...")

        self.processor = XCLIPProcessor.from_pretrained(self.model_path)

        # Try to load with SDPA (Scaled Dot-Product Attention) for 15-40% faster inference
        # SDPA requires PyTorch 2.0+ and compatible hardware
        try:
            self.model = XCLIPModel.from_pretrained(
                self.model_path,
                attn_implementation="sdpa",
            )
            logger.info("X-CLIP loaded with SDPA attention (optimized)")
        except (ValueError, ImportError) as e:
            # Fall back to default attention if SDPA is not supported
            logger.warning(f"SDPA not available, falling back to default attention: {e}")
            self.model = XCLIPModel.from_pretrained(self.model_path)

        # Move to device
        if "cuda" in self.device and torch.cuda.is_available():
            self.model = self.model.to(self.device)  # type: ignore[arg-type]
            logger.info(f"ActionRecognizer loaded on {self.device}")
        else:
            self.device = "cpu"
            logger.info("ActionRecognizer using CPU (CUDA not available)")

        self.model.eval()
        logger.info("ActionRecognizer loaded successfully")

        return self

    def unload_model(self) -> None:
        """Unload the model from memory to free VRAM.

        Call this when the model is no longer needed to release GPU resources.
        """
        if self.model is not None:
            del self.model
            self.model = None
        if self.processor is not None:
            del self.processor
            self.processor = None

        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        logger.info("ActionRecognizer unloaded")

    def _sample_frames(
        self,
        frames: list[Image.Image | np.ndarray],
        num_frames: int = 16,
    ) -> list[Image.Image]:
        """Sample frames evenly from input sequence.

        If the input has fewer frames than required, the last frame is repeated
        to pad the sequence. If the input has more frames, frames are sampled
        at regular intervals to cover the entire sequence.

        Args:
            frames: List of input frames (PIL Images or numpy arrays)
            num_frames: Number of frames to sample (default: 16 for NEM-3908)

        Returns:
            List of PIL Images with exactly num_frames elements.

        Raises:
            ValueError: If frames list is empty.
        """
        if not frames:
            raise ValueError("Cannot sample from empty frame list")

        # Convert numpy arrays to PIL Images
        pil_frames: list[Image.Image] = []
        for frame in frames:
            if isinstance(frame, np.ndarray):
                # Ensure RGB format
                arr = frame
                if len(arr.shape) == 2:
                    # Grayscale to RGB
                    arr = np.stack([arr] * 3, axis=-1)
                elif arr.shape[2] == 4:
                    # RGBA to RGB
                    arr = arr[:, :, :3]
                pil_frames.append(Image.fromarray(arr))
            else:
                # Ensure RGB mode for PIL Image
                pil_frame = frame if frame.mode == "RGB" else frame.convert("RGB")
                pil_frames.append(pil_frame)

        # Handle case where we have fewer frames than needed
        if len(pil_frames) <= num_frames:
            # Pad by repeating last frame
            result = pil_frames.copy()
            while len(result) < num_frames:
                result.append(pil_frames[-1])
            return result

        # Sample frames evenly across the sequence
        indices = np.linspace(0, len(pil_frames) - 1, num_frames, dtype=int)
        return [pil_frames[i] for i in indices]

    def recognize_action(
        self,
        frames: list[np.ndarray | Image.Image],
        actions: list[str] | None = None,
    ) -> ActionResult:
        """Recognize action from a sequence of video frames.

        This method takes a sequence of frames and classifies the action
        being performed using zero-shot classification with X-CLIP.

        Args:
            frames: List of video frames as PIL Images or numpy arrays.
                   Ideally 8-32 frames covering the action duration.
            actions: Optional custom list of action labels to classify.
                    If None, uses SECURITY_ACTIONS.

        Returns:
            ActionResult containing the recognized action, confidence,
            whether it's suspicious, and scores for all actions.

        Raises:
            RuntimeError: If model is not loaded.
            ValueError: If frames list is empty.
        """
        if self.model is None or self.processor is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        if not frames:
            raise ValueError("Frames list cannot be empty")

        # Use default security actions if not provided
        if actions is None:
            actions = SECURITY_ACTIONS

        # Sample frames to the required number
        sampled_frames = self._sample_frames(frames, self.num_frames)

        # Create text prompts for each action
        # Using "a person {action}" format for better zero-shot performance
        text_prompts = [f"a person {action}" for action in actions]

        # Process inputs
        # X-CLIP expects videos as list of lists of frames: [[frame1, frame2, ...]]
        inputs = self.processor(
            text=text_prompts,
            videos=[sampled_frames],  # List containing one video (list of frames)
            return_tensors="pt",
            padding=True,
        )

        # Move inputs to device
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        # Run inference
        with torch.inference_mode():
            outputs = self.model(**inputs)
            # logits_per_video shape: (num_videos, num_actions) = (1, len(actions))
            logits = outputs.logits_per_video
            probs = torch.softmax(logits, dim=1)[0]

        # Get results
        probs_np = probs.cpu().numpy()
        top_idx = int(probs_np.argmax())
        top_action = actions[top_idx]
        top_confidence = float(probs_np[top_idx])

        # Build all scores dictionary
        all_scores = {action: round(float(probs_np[i]), 4) for i, action in enumerate(actions)}

        # Determine if action is suspicious
        is_suspicious = top_action in SUSPICIOUS_ACTIONS

        return ActionResult(
            action=top_action,
            confidence=round(top_confidence, 4),
            is_suspicious=is_suspicious,
            all_scores=all_scores,
        )

    def recognize_action_batch(
        self,
        frame_sequences: list[list[np.ndarray | Image.Image]],
        actions: list[str] | None = None,
    ) -> list[ActionResult]:
        """Recognize actions from multiple video sequences in batch.

        This is more efficient than calling recognize_action() multiple times
        when processing several video clips.

        Args:
            frame_sequences: List of frame sequences, where each sequence
                           is a list of PIL Images or numpy arrays.
            actions: Optional custom list of action labels.

        Returns:
            List of ActionResult objects, one per input sequence.

        Raises:
            RuntimeError: If model is not loaded.
            ValueError: If frame_sequences is empty or contains empty sequences.
        """
        if self.model is None or self.processor is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        if not frame_sequences:
            raise ValueError("Frame sequences list cannot be empty")

        # Use default security actions if not provided
        if actions is None:
            actions = SECURITY_ACTIONS

        # Process each sequence
        all_sampled: list[list[Image.Image]] = []
        for seq in frame_sequences:
            if not seq:
                raise ValueError("Frame sequence cannot be empty")
            all_sampled.append(self._sample_frames(seq, self.num_frames))

        # Create text prompts
        text_prompts = [f"a person {action}" for action in actions]

        # Process inputs - all videos at once
        inputs = self.processor(
            text=text_prompts,
            videos=all_sampled,
            return_tensors="pt",
            padding=True,
        )

        # Move inputs to device
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        # Run inference
        with torch.inference_mode():
            outputs = self.model(**inputs)
            logits = outputs.logits_per_video  # Shape: (num_videos, num_actions)
            probs = torch.softmax(logits, dim=1)

        # Build results
        results: list[ActionResult] = []
        probs_np = probs.cpu().numpy()

        for i in range(len(frame_sequences)):
            video_probs = probs_np[i]
            top_idx = int(video_probs.argmax())
            top_action = actions[top_idx]
            top_confidence = float(video_probs[top_idx])

            all_scores = {
                action: round(float(video_probs[j]), 4) for j, action in enumerate(actions)
            }

            results.append(
                ActionResult(
                    action=top_action,
                    confidence=round(top_confidence, 4),
                    is_suspicious=top_action in SUSPICIOUS_ACTIONS,
                    all_scores=all_scores,
                )
            )

        return results


def load_action_recognizer(model_path: str, device: str = "cuda:0") -> ActionRecognizer:
    """Factory function for model registry integration.

    Creates and loads an ActionRecognizer instance. This function is designed
    to be used with the OnDemandModelManager's loader_fn parameter.

    Args:
        model_path: Path to X-CLIP model directory or HuggingFace model ID
        device: Device to run inference on

    Returns:
        Loaded ActionRecognizer instance ready for inference.

    Example:
        from ai.enrichment.model_manager import ModelConfig, ModelPriority

        config = ModelConfig(
            name="action_recognizer",
            vram_mb=1500,
            priority=ModelPriority.LOW,
            loader_fn=lambda: load_action_recognizer("/models/xclip"),
            unloader_fn=lambda m: m.unload_model(),
        )
    """
    recognizer = ActionRecognizer(model_path=model_path, device=device)
    recognizer.load_model()
    return recognizer
