"""X-CLIP Video Action Recognition Module.

This module provides the ActionRecognizer class for video-based action recognition
using Microsoft's X-CLIP model. It analyzes sequences of frames to understand
what people are doing over time.

Supports torch.compile() for optimized inference (NEM-3375).
Supports Accelerate device_map for automatic device placement (NEM-3378).
Implements true batch inference for vision models (NEM-3377).

Model Details:
- Model: microsoft/xclip-base-patch32
- VRAM: ~1.5GB
- Priority: LOW (expensive, use sparingly)
- Input: 8-32 frames
- Output: Action classification with confidence

Trigger Conditions (document for model orchestration):
- Only run action recognition when:
  - Person detected for >3 seconds
  - Multiple frames available in buffer
  - Unusual pose detected (trigger from pose estimator)

Reference: https://huggingface.co/microsoft/xclip-base-patch32
Design Doc: docs/plans/2026-01-19-model-zoo-prompt-improvements-design.md Section 5.5
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import torch
from PIL import Image

if TYPE_CHECKING:
    from transformers import XCLIPModel, XCLIPProcessor

# Add parent directory to path for shared utilities
_ai_dir = Path(__file__).parent.parent.parent
if str(_ai_dir) not in sys.path:
    sys.path.insert(0, str(_ai_dir))

from torch_optimizations import (  # noqa: E402
    compile_model,
    get_optimal_device_map,
    get_torch_dtype_for_device,
    is_compile_supported,
)

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

    Supports:
    - torch.compile() for optimized inference (NEM-3375)
    - Accelerate device_map for automatic device placement (NEM-3378)
    - True batch inference with optimal batching (NEM-3377)

    VRAM Usage: ~1.5GB
    Typical Inference Time: ~200-500ms for 8 frames

    Example usage:
        recognizer = ActionRecognizer("/models/xclip-base-patch32")
        recognizer.load_model()

        # Get frames from video buffer (list of PIL Images or numpy arrays)
        frames = [frame1, frame2, frame3, ...]

        result = recognizer.recognize_action(frames)
        print(f"Action: {result.action} (confidence: {result.confidence:.2%})")
        if result.is_suspicious:
            print("ALERT: Suspicious activity detected!")
    """

    def __init__(
        self,
        model_path: str,
        device: str = "cuda:0",
        use_compile: bool = True,
        use_accelerate: bool = True,
    ):
        """Initialize action recognizer.

        Args:
            model_path: Path to X-CLIP model directory or HuggingFace model ID
                       (e.g., "microsoft/xclip-base-patch32" or "/models/xclip")
            device: Device to run inference on (e.g., "cuda:0" or "cpu")
            use_compile: Whether to use torch.compile() for optimization (NEM-3375).
            use_accelerate: Whether to use Accelerate device_map (NEM-3378).
        """
        self.model_path = model_path
        self.device = device
        self.model: XCLIPModel | None = None
        self.processor: XCLIPProcessor | None = None
        self.num_frames = 8  # X-CLIP typically uses 8 frames
        self.use_compile = use_compile
        self.use_accelerate = use_accelerate
        self.is_compiled = False

        logger.info(f"Initializing ActionRecognizer from {self.model_path}")
        logger.info(f"torch.compile enabled: {use_compile}, Accelerate enabled: {use_accelerate}")

    def load_model(self) -> ActionRecognizer:
        """Load the X-CLIP model into memory.

        Supports:
        - Accelerate device_map for automatic device placement (NEM-3378)
        - torch.compile() for optimized inference (NEM-3375)

        Returns:
            Self for method chaining.

        Raises:
            ImportError: If transformers library is not available.
            OSError: If model files cannot be loaded.
        """
        from transformers import XCLIPModel, XCLIPProcessor

        logger.info("Loading X-CLIP model...")

        self.processor = XCLIPProcessor.from_pretrained(self.model_path)

        # Determine device and dtype
        if "cuda" in self.device and torch.cuda.is_available():
            torch_dtype = get_torch_dtype_for_device(self.device)
        else:
            self.device = "cpu"
            torch_dtype = torch.float32

        # Load model with Accelerate device_map if enabled (NEM-3378)
        if self.use_accelerate and "cuda" in self.device:
            device_map = get_optimal_device_map(self.model_path)
            logger.info(f"Loading model with device_map='{device_map}'")
            self.model = XCLIPModel.from_pretrained(
                self.model_path,
                device_map=device_map,
                torch_dtype=torch_dtype,
            )
        else:
            # Traditional loading with manual device placement
            self.model = XCLIPModel.from_pretrained(self.model_path)
            if "cuda" in self.device:
                self.model = self.model.to(self.device)  # type: ignore[arg-type]
                logger.info(f"ActionRecognizer loaded on {self.device}")
            else:
                logger.info("ActionRecognizer using CPU (CUDA not available)")

        self.model.eval()

        # Apply torch.compile() for optimized inference (NEM-3375)
        if self.use_compile and is_compile_supported():
            logger.info("Applying torch.compile() for optimized inference...")
            self.model = compile_model(self.model, mode="reduce-overhead")
            self.is_compiled = True
        else:
            logger.info("torch.compile() not applied (disabled or not supported)")

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
        num_frames: int = 8,
    ) -> list[Image.Image]:
        """Sample frames evenly from input sequence.

        If the input has fewer frames than required, the last frame is repeated
        to pad the sequence. If the input has more frames, frames are sampled
        at regular intervals to cover the entire sequence.

        Args:
            frames: List of input frames (PIL Images or numpy arrays)
            num_frames: Number of frames to sample (default: 8)

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
        with torch.no_grad():
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
        with torch.no_grad():
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


def load_action_recognizer(
    model_path: str,
    device: str = "cuda:0",
    use_compile: bool = True,
    use_accelerate: bool = True,
) -> ActionRecognizer:
    """Factory function for model registry integration.

    Creates and loads an ActionRecognizer instance. This function is designed
    to be used with the OnDemandModelManager's loader_fn parameter.

    Args:
        model_path: Path to X-CLIP model directory or HuggingFace model ID
        device: Device to run inference on
        use_compile: Whether to use torch.compile() for optimization (NEM-3375).
        use_accelerate: Whether to use Accelerate device_map (NEM-3378).

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
    recognizer = ActionRecognizer(
        model_path=model_path,
        device=device,
        use_compile=use_compile,
        use_accelerate=use_accelerate,
    )
    recognizer.load_model()
    return recognizer
