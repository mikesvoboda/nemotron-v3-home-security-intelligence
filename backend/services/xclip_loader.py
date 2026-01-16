"""X-CLIP model loader for temporal action recognition.

This module provides async loading of X-CLIP models for classifying actions
in video sequences (multiple frames). X-CLIP extends CLIP for video understanding
by adding temporal attention mechanisms.

The model analyzes sequences of frames to detect security-relevant actions like:
- Person loitering, approaching door, running away
- Looking around suspiciously, trying door handle
- Walking normally, delivering package

Reference: https://huggingface.co/microsoft/xclip-base-patch32
"""

from __future__ import annotations

import asyncio
from typing import Any

from PIL import Image

from backend.core.logging import get_logger

logger = get_logger(__name__)

# Security-focused action prompts for home security monitoring
# These prompts are designed to capture suspicious vs normal behaviors
SECURITY_ACTION_PROMPTS = [
    "a person loitering",
    "a person approaching a door",
    "a person running away",
    "a person looking around suspiciously",
    "a person trying a door handle",
    "a person walking normally",
    "a person delivering a package",
    "a person checking windows",
    "a person hiding near bushes",
    "a person taking photos of house",
    "a person knocking on door",
    "a person ringing doorbell",
    "a person leaving package at door",
    "a person vandalizing property",
    "a person breaking in",
]


async def load_xclip_model(model_path: str) -> Any:
    """Load an X-CLIP model from local path or HuggingFace.

    This function loads the X-CLIP model for temporal action recognition
    in video sequences.

    Args:
        model_path: Local model path or HuggingFace model path
            (e.g., "/export/ai_models/model-zoo/xclip-base" or "microsoft/xclip-base-patch32")

    Returns:
        Dictionary containing:
            - model: The X-CLIP model instance
            - processor: The X-CLIP processor for video/image preprocessing

    Raises:
        ImportError: If transformers is not installed
        RuntimeError: If model loading fails
    """
    try:
        from transformers import XCLIPModel, XCLIPProcessor

        logger.info(f"Loading X-CLIP model from {model_path}")

        loop = asyncio.get_event_loop()

        # Load model and processor in thread pool to avoid blocking
        def _load() -> dict[str, Any]:
            processor = XCLIPProcessor.from_pretrained(model_path)
            model = XCLIPModel.from_pretrained(model_path)

            # Move to GPU if available and use float16 for memory efficiency
            try:
                import torch

                if torch.cuda.is_available():
                    model = model.cuda().half()
                    logger.info("X-CLIP model moved to CUDA with float16")
            except ImportError:
                # torch not installed, model will run on CPU.
                # CPU fallback is acceptable for X-CLIP model inference.
                # See: NEM-2540 for rationale
                pass

            # Set to eval mode
            model.eval()

            return {"model": model, "processor": processor}

        result = await loop.run_in_executor(None, _load)

        logger.info(f"Successfully loaded X-CLIP model from {model_path}")
        return result

    except ImportError as e:
        logger.warning("transformers package not installed. Install with: pip install transformers")
        raise ImportError(
            "transformers package required for X-CLIP. Install with: pip install transformers"
        ) from e

    except Exception as e:
        logger.error("Failed to load X-CLIP model", exc_info=True, extra={"model_path": model_path})
        raise RuntimeError(f"Failed to load X-CLIP model: {e}") from e


async def classify_actions(
    model_dict: dict[str, Any],
    frames: list[Image.Image],
    prompts: list[str] | None = None,
    top_k: int = 3,
) -> dict[str, Any]:
    """Classify actions in a sequence of frames using X-CLIP.

    This function takes multiple frames and classifies the action being
    performed across the temporal sequence. X-CLIP is designed for video
    understanding and captures temporal patterns across frames.

    Args:
        model_dict: Dictionary containing model and processor from load_xclip_model
        frames: List of PIL Images representing video frames (ideally 8 frames)
        prompts: Custom action prompts to classify against.
            If None, uses SECURITY_ACTION_PROMPTS.
        top_k: Number of top predictions to return (default 3)

    Returns:
        Dictionary containing:
            - detected_action: Top predicted action label
            - confidence: Confidence score for top action (0-1)
            - top_actions: List of (action, confidence) tuples for top_k predictions
            - all_scores: Dictionary mapping all prompts to their scores

    Raises:
        ValueError: If frames list is empty or contains only None values
        RuntimeError: If classification fails
    """
    if not frames:
        raise ValueError("At least one frame is required for action classification")

    # Filter out None frames (can occur if image loading/cropping fails)
    valid_frames = [f for f in frames if f is not None]

    if not valid_frames:
        raise ValueError("No valid frames provided for action classification (all frames are None)")

    # Log warning if some frames were None
    if len(valid_frames) < len(frames):
        logger.warning(
            f"X-CLIP received {len(frames)} frames but {len(frames) - len(valid_frames)} "
            f"were None and filtered out. Proceeding with {len(valid_frames)} valid frames."
        )

    # Use valid frames for classification
    frames = valid_frames

    if prompts is None:
        prompts = SECURITY_ACTION_PROMPTS

    try:
        import torch

        model = model_dict["model"]
        processor = model_dict["processor"]

        loop = asyncio.get_event_loop()

        def _classify() -> dict[str, Any]:
            # X-CLIP expects 8 frames for optimal performance
            # If we have fewer, duplicate frames to reach 8
            # If we have more, sample uniformly to get 8
            num_frames = 8
            if len(frames) < num_frames:
                # Duplicate last frame to fill
                padded_frames = frames + [frames[-1]] * (num_frames - len(frames))
            elif len(frames) > num_frames:
                # Sample uniformly
                indices = [int(i * len(frames) / num_frames) for i in range(num_frames)]
                padded_frames = [frames[i] for i in indices]
            else:
                padded_frames = frames

            # Prepare inputs for X-CLIP
            # X-CLIP expects videos as list of frames
            inputs = processor(
                text=prompts,
                videos=padded_frames,  # List of PIL images
                return_tensors="pt",
                padding=True,
            )

            # Move to GPU if model is on GPU
            device = next(model.parameters()).device
            inputs = {k: v.to(device) for k, v in inputs.items()}

            # Handle dtype for float16 models
            if next(model.parameters()).dtype == torch.float16 and "pixel_values" in inputs:
                inputs["pixel_values"] = inputs["pixel_values"].half()

            # Run inference
            with torch.no_grad():
                outputs = model(**inputs)

            # Get similarity scores (logits per video)
            logits_per_video = outputs.logits_per_video
            probs = torch.softmax(logits_per_video, dim=-1)
            probs_np = probs.squeeze(0).cpu().numpy()

            # Build results
            scores = {prompt: float(prob) for prompt, prob in zip(prompts, probs_np, strict=True)}

            # Sort by confidence
            sorted_actions = sorted(scores.items(), key=lambda x: x[1], reverse=True)

            top_actions = sorted_actions[:top_k]
            detected_action = sorted_actions[0][0]
            confidence = sorted_actions[0][1]

            return {
                "detected_action": detected_action,
                "confidence": confidence,
                "top_actions": top_actions,
                "all_scores": scores,
            }

        result = await loop.run_in_executor(None, _classify)
        logger.debug(
            f"X-CLIP classified action: {result['detected_action']} "
            f"(confidence: {result['confidence']:.2%})"
        )
        return result

    except Exception as e:
        logger.error("X-CLIP action classification failed", exc_info=True)
        raise RuntimeError(f"X-CLIP classification failed: {e}") from e


def sample_frames_from_batch(
    frame_paths: list[str],
    target_count: int = 8,
) -> list[str]:
    """Sample frames uniformly from a batch for X-CLIP processing.

    X-CLIP works best with 8 frames spanning the action. This function
    samples frames uniformly from a larger batch.

    Args:
        frame_paths: List of frame file paths
        target_count: Number of frames to sample (default 8)

    Returns:
        List of sampled frame paths
    """
    if len(frame_paths) <= target_count:
        return frame_paths

    # Sample uniformly
    step = len(frame_paths) / target_count
    indices = [int(i * step) for i in range(target_count)]
    return [frame_paths[i] for i in indices]


def is_suspicious_action(action: str) -> bool:
    """Check if a detected action is considered suspicious.

    Args:
        action: Detected action string

    Returns:
        True if the action is suspicious/concerning
    """
    suspicious_keywords = [
        "loitering",
        "suspiciously",
        "running away",
        "trying",
        "hiding",
        "vandalizing",
        "breaking",
        "checking windows",
        "taking photos",
    ]
    action_lower = action.lower()
    return any(keyword in action_lower for keyword in suspicious_keywords)


def get_action_risk_weight(action: str) -> float:
    """Get a risk weight for an action to influence overall risk scoring.

    Args:
        action: Detected action string

    Returns:
        Risk weight from 0.0 (no risk) to 1.0 (high risk)
    """
    action_lower = action.lower()

    # High risk actions
    if any(
        kw in action_lower for kw in ["breaking in", "vandalizing", "trying door handle", "hiding"]
    ):
        return 1.0

    # Medium risk actions
    if any(
        kw in action_lower
        for kw in ["loitering", "suspiciously", "running away", "taking photos", "checking"]
    ):
        return 0.7

    # Low risk / normal actions
    if any(
        kw in action_lower
        for kw in ["delivering", "knocking", "ringing", "leaving package", "walking normally"]
    ):
        return 0.2

    # Neutral
    return 0.5
