"""X-CLIP model loader for temporal action recognition.

This module provides async loading of X-CLIP models for classifying actions
in video sequences (multiple frames). X-CLIP extends CLIP for video understanding
by adding temporal attention mechanisms.

The model analyzes sequences of frames to detect security-relevant actions like:
- Person loitering, approaching door, running away
- Looking around suspiciously, trying door handle
- Walking normally, delivering package

Model Configuration (NEM-3908):
- Model: microsoft/xclip-base-patch16-16-frames
- Frames: 16 (upgraded from 8 for +4% accuracy)
- Patch size: 16 (finer spatial resolution than patch32)
- VRAM: ~2GB

Reference: https://huggingface.co/microsoft/xclip-base-patch16-16-frames
"""

from __future__ import annotations

import asyncio
from typing import Any, TypedDict

from PIL import Image

from backend.core.logging import get_logger

logger = get_logger(__name__)

# ==============================================================================
# Hierarchical Security Action Categories (NEM-3913)
# ==============================================================================
# Action prompts organized by risk level with category-specific thresholds.
# This hierarchical structure enables better risk assessment by the LLM.


class ActionCategoryConfig(TypedDict):
    """Configuration for an action category."""

    prompts: list[str]
    threshold: float


ACTION_PROMPTS_V2: dict[str, ActionCategoryConfig] = {
    "high_risk": {
        "prompts": [
            "a person breaking into a building through a window",
            "a person forcing open a door with tools",
            "a person smashing or breaking glass",
            "a person climbing over a fence",
            "a person picking or tampering with a lock",
            "a person vandalizing property",
            "a person running away quickly after an action",
            # Legacy prompts for compatibility
            "a person breaking in",
            "a person vandalizing property",
        ],
        "threshold": 0.20,  # Low threshold - don't miss these
    },
    "suspicious": {
        "prompts": [
            "a person loitering and looking around suspiciously",
            "a person repeatedly walking past the same location",
            "a person hiding behind bushes or objects",
            "a person casing a house by looking at windows and doors",
            "a person photographing security cameras or locks",
            "a person checking if anyone is home",
            "a person carrying tools at night",
            "a person peeking into windows",
            # Legacy prompts for compatibility
            "a person loitering",
            "a person looking around suspiciously",
            "a person trying a door handle",
            "a person checking windows",
            "a person hiding near bushes",
            "a person taking photos of house",
        ],
        "threshold": 0.25,
    },
    "approaching": {
        "prompts": [
            "a person approaching a front door",
            "a person walking up a driveway",
            "a person approaching a side entrance",
            "a person approaching a garage",
            # Legacy prompts for compatibility
            "a person approaching a door",
        ],
        "threshold": 0.30,
    },
    "delivery": {
        "prompts": [
            "a delivery driver carrying a package to a door",
            "a mail carrier delivering mail",
            "a person leaving a package at a door",
            "a food delivery person with a bag",
            # Legacy prompts for compatibility
            "a person delivering a package",
            "a person leaving package at door",
        ],
        "threshold": 0.35,
    },
    "normal": {
        "prompts": [
            "a person walking casually on a sidewalk",
            "a person jogging or running for exercise",
            "a person walking a dog",
            "a person checking a mailbox",
            "a person mowing a lawn or doing yard work",
            "a person knocking politely on a door",
            "a person ringing a doorbell and waiting",
            "a person waving or greeting someone",
            # Legacy prompts for compatibility
            "a person walking normally",
            "a person knocking on door",
            "a person ringing doorbell",
        ],
        "threshold": 0.40,
    },
    "stationary": {
        "prompts": [
            "a person standing still and waiting",
            "a person talking on a phone",
            "a person looking at their phone",
            "a person sitting on steps or a porch",
        ],
        "threshold": 0.40,
    },
    "fleeing": {
        "prompts": [
            "a person running away from a location",
            "a person quickly leaving after suspicious activity",
            "a person fleeing the scene",
            # Legacy prompts for compatibility
            "a person running away",
        ],
        "threshold": 0.25,
    },
}


def get_all_action_prompts() -> list[str]:
    """Get flattened list of all action prompts from hierarchical categories.

    Returns:
        List of all prompts across all categories.
    """
    return [p for cat in ACTION_PROMPTS_V2.values() for p in cat["prompts"]]


def get_action_risk_level(matched_action: str) -> str:
    """Map detected action to risk level.

    Args:
        matched_action: The action that was matched.

    Returns:
        Risk level string: "critical", "high", "medium", or "low".
    """
    for category, config in ACTION_PROMPTS_V2.items():
        if matched_action in config["prompts"]:
            if category in ["high_risk"]:
                return "critical"
            elif category in ["suspicious", "fleeing"]:
                return "high"
            elif category in ["approaching"]:
                return "medium"
            else:
                return "low"
    return "low"


def get_action_threshold(category: str) -> float:
    """Get confidence threshold for an action category.

    Args:
        category: Category name (e.g., "high_risk", "suspicious").

    Returns:
        Confidence threshold for the category, or 0.35 as default.
    """
    config = ACTION_PROMPTS_V2.get(category)
    if config is None:
        return 0.35
    return config["threshold"]


def get_action_category(matched_action: str) -> str | None:
    """Get category name for a matched action prompt.

    Args:
        matched_action: The action that was matched.

    Returns:
        Category name or None if not found.
    """
    for category, config in ACTION_PROMPTS_V2.items():
        if matched_action in config["prompts"]:
            return category
    return None


# ==============================================================================
# Backward Compatibility - Legacy Constants (NEM-3913)
# ==============================================================================
# These constants are maintained for backward compatibility with existing code.
# New code should use the hierarchical ACTION_PROMPTS_V2 structure.

# Security-focused action prompts for home security monitoring
# These prompts are designed to capture suspicious vs normal behaviors
SECURITY_ACTION_PROMPTS = get_all_action_prompts()


async def load_xclip_model(model_path: str) -> Any:
    """Load an X-CLIP model from local path or HuggingFace.

    This function loads the X-CLIP model for temporal action recognition
    in video sequences.

    Args:
        model_path: Local model path or HuggingFace model path
            (e.g., "/export/ai_models/model-zoo/xclip-base-patch16-16-frames"
            or "microsoft/xclip-base-patch16-16-frames")

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


def _is_valid_pil_image(obj: Any) -> bool:
    """Check if an object is a valid PIL Image.

    Args:
        obj: Object to validate

    Returns:
        True if obj is a valid PIL Image with accessible size/mode
    """
    if obj is None:
        return False
    if not isinstance(obj, Image.Image):
        return False
    try:
        # Verify image is accessible (not closed/corrupted)
        _ = obj.size
        _ = obj.mode
        return True
    except Exception:
        return False


def _convert_to_numpy_safe(pil_image: Image.Image) -> Any | None:
    """Safely convert a PIL Image to a numpy array.

    PIL images can be lazy-loaded and may fail when attempting to access
    pixel data (e.g., corrupted or truncated files). This function catches
    those failures and returns None instead of raising.

    Args:
        pil_image: PIL Image to convert

    Returns:
        Numpy array of the image, or None if conversion fails
    """
    try:
        import numpy as np

        # Force load the image data (PIL lazy-loads by default)
        pil_image.load()

        # Convert to numpy array
        arr = np.array(pil_image)

        # Validate the result has expected properties
        if arr is None:
            return None
        if not hasattr(arr, "shape"):
            return None
        if len(arr.shape) < 2:  # Must be at least 2D (height, width)
            return None
        if arr.shape[0] == 0 or arr.shape[1] == 0:  # Must have non-zero dimensions
            return None

        return arr
    except Exception:
        # Any failure during load/conversion returns None
        return None


def _validate_and_convert_frames(frames: list[Image.Image]) -> list[Image.Image]:
    """Validate frames can be converted to numpy and filter out invalid ones.

    This performs deep validation by actually attempting numpy conversion,
    which catches corrupted/truncated images that pass basic PIL validation
    but fail when pixel data is accessed.

    Args:
        frames: List of PIL Images to validate

    Returns:
        List of validated PIL Images (invalid frames filtered out)
    """
    valid_frames = []
    for frame in frames:
        if not _is_valid_pil_image(frame):
            continue

        # Deep validation: attempt numpy conversion
        arr = _convert_to_numpy_safe(frame)
        if arr is not None:
            valid_frames.append(frame)
        else:
            logger.debug(
                "Frame passed PIL validation but failed numpy conversion - likely corrupted"
            )

    return valid_frames


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
        frames: List of PIL Images representing video frames (ideally 16 frames
            for xclip-base-patch16-16-frames model)
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
        ValueError: If frames list is empty or contains only invalid/None values
        RuntimeError: If classification fails
    """
    if not frames:
        raise ValueError("At least one frame is required for action classification")

    # First pass: filter out None and basic invalid PIL Images
    pil_valid_frames = [f for f in frames if _is_valid_pil_image(f)]

    if not pil_valid_frames:
        raise ValueError(
            "No valid frames provided for action classification "
            "(all frames are None or invalid PIL Images)"
        )

    # Second pass: deep validation - verify numpy conversion works
    # This catches corrupted/truncated images that pass PIL validation
    # but fail when pixel data is accessed (the source of .shape errors)
    valid_frames = _validate_and_convert_frames(pil_valid_frames)

    if not valid_frames:
        raise ValueError(
            "No valid frames provided for action classification "
            "(all frames failed numpy conversion - likely corrupted images)"
        )

    # Log warning if some frames were invalid
    total_filtered = len(frames) - len(valid_frames)
    if total_filtered > 0:
        pil_invalid = len(frames) - len(pil_valid_frames)
        numpy_invalid = len(pil_valid_frames) - len(valid_frames)
        logger.warning(
            f"X-CLIP received {len(frames)} frames but {total_filtered} were invalid: "
            f"{pil_invalid} failed PIL validation, {numpy_invalid} failed numpy conversion. "
            f"Proceeding with {len(valid_frames)} valid frames."
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
            import numpy as np

            # X-CLIP base-patch16-16-frames model expects 16 frames for optimal performance
            # This provides ~4% improved accuracy over the 8-frame variant (NEM-3908)
            # If we have fewer, duplicate frames to reach 16
            # If we have more, sample uniformly to get 16
            num_frames = 16
            if len(frames) < num_frames:
                # Duplicate last frame to fill
                padded_frames = frames + [frames[-1]] * (num_frames - len(frames))
            elif len(frames) > num_frames:
                # Sample uniformly
                indices = [int(i * len(frames) / num_frames) for i in range(num_frames)]
                padded_frames = [frames[i] for i in indices]
            else:
                padded_frames = frames

            # Final safety check: convert frames to numpy arrays explicitly
            # This catches any edge cases where PIL images become invalid after validation
            # Also convert to RGB to ensure consistent color mode for X-CLIP processor
            # IMPORTANT: Pass numpy arrays to processor to avoid lazy-loading issues
            # that can cause pixel_values to be None (NEM-3506)
            validated_frames: list[Any] = []
            for i, frame in enumerate(padded_frames):
                try:
                    # Force load and convert to numpy to validate
                    frame.load()
                    # Convert to RGB to ensure consistent color mode
                    # X-CLIP processor expects RGB format - other modes (RGBA, L, P) can cause failures
                    rgb_frame = frame.convert("RGB") if frame.mode != "RGB" else frame
                    arr = np.array(rgb_frame)
                    if arr is None or not hasattr(arr, "shape") or len(arr.shape) < 2:
                        raise ValueError(f"Frame {i} produced invalid numpy array")
                    # Validate shape is (H, W, C) with C=3 for RGB
                    if len(arr.shape) != 3 or arr.shape[2] != 3:
                        raise ValueError(
                            f"Frame {i} has invalid shape {arr.shape}, expected (H, W, 3)"
                        )
                    # Validate pixel value range (uint8: 0-255)
                    if arr.dtype != np.uint8:
                        # Convert to uint8 if needed
                        if arr.max() <= 1.0:
                            arr = (arr * 255).astype(np.uint8)
                        else:
                            arr = arr.astype(np.uint8)
                    # Use numpy array directly - avoids PIL lazy-loading issues
                    # VideoMAEImageProcessor accepts numpy arrays in (H, W, C) format
                    validated_frames.append(arr)
                except Exception as e:
                    logger.warning(f"Frame {i} failed final validation: {e}")
                    # Try to use another valid frame as replacement
                    if validated_frames:
                        validated_frames.append(validated_frames[-1])
                    else:
                        # Skip this frame - will cause fewer frames if at start
                        pass

            if not validated_frames:
                raise RuntimeError(
                    "All frames failed final numpy validation before X-CLIP processing"
                )

            # Re-pad if we lost frames during validation
            while len(validated_frames) < num_frames and validated_frames:
                validated_frames.append(validated_frames[-1])

            # Log frame statistics for debugging
            logger.debug(
                f"X-CLIP processing {len(validated_frames)} frames, "
                f"shape: {validated_frames[0].shape if validated_frames else 'N/A'}, "
                f"dtype: {validated_frames[0].dtype if validated_frames else 'N/A'}"
            )

            # Prepare inputs for X-CLIP
            # NOTE: Despite the X-CLIP model being designed for video, the XCLIPProcessor
            # in transformers 4.57+ uses `images=` parameter for video frames, NOT `videos=`.
            # The `videos=` parameter returns None for pixel_values.
            # Pass frames directly (list of numpy arrays) - no wrapping in outer list.
            try:
                inputs = processor(
                    text=prompts,
                    images=validated_frames,  # Use images= for video frames (transformers 4.57+)
                    return_tensors="pt",
                    padding=True,
                )
            except AttributeError as e:
                # This catches the "'NoneType' object has no attribute 'shape'" error
                # that occurs inside the HuggingFace processor
                raise RuntimeError(
                    f"X-CLIP processor failed - likely corrupted frame data: {e}"
                ) from e

            # Validate processor output - pixel_values can be None if frames are invalid
            # This is the root cause of "'NoneType' object has no attribute 'shape'" errors
            if inputs is None:
                raise RuntimeError("X-CLIP processor returned None - input frames may be invalid")

            pixel_values = inputs.get("pixel_values")
            if pixel_values is None:
                raise RuntimeError(
                    "X-CLIP processor returned None for pixel_values - "
                    "frames may be corrupted or in an unsupported format. "
                    f"Attempted to process {len(validated_frames)} frames."
                )

            # Validate tensor shape: expected [batch, num_frames, channels, height, width]
            if not hasattr(pixel_values, "shape"):
                raise RuntimeError(
                    f"X-CLIP pixel_values has no shape attribute - "
                    f"got type {type(pixel_values).__name__}"
                )

            if len(pixel_values.shape) != 5:
                raise RuntimeError(
                    f"X-CLIP pixel_values has unexpected shape {pixel_values.shape} - "
                    f"expected 5 dimensions [batch, frames, channels, height, width]"
                )

            logger.debug(
                f"X-CLIP processor output validated: pixel_values shape={pixel_values.shape}"
            )

            # Move to GPU if model is on GPU
            device = next(model.parameters()).device
            inputs = {k: v.to(device) if v is not None else v for k, v in inputs.items()}

            # Handle dtype for float16 models
            if next(model.parameters()).dtype == torch.float16 and "pixel_values" in inputs:
                inputs["pixel_values"] = inputs["pixel_values"].half()

            # Run inference
            with torch.inference_mode():
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
    target_count: int = 16,
) -> list[str]:
    """Sample frames uniformly from a batch for X-CLIP processing.

    X-CLIP base-patch16-16-frames model works best with 16 frames spanning
    the action. This function samples frames uniformly from a larger batch.

    Args:
        frame_paths: List of frame file paths
        target_count: Number of frames to sample (default 16 for NEM-3908 upgrade)

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
