"""Weather classification model loader.

This module provides async loading of the Weather-Image-Classification model
(prithivMLmods/Weather-Image-Classification) for classifying weather conditions
from full-frame security camera images.

The model uses SigLIP architecture fine-tuned for weather classification with 5 classes:
- cloudy/overcast
- foggy/hazy
- rain/storm
- snow/frosty
- sun/clear

Model details:
- HuggingFace: prithivMLmods/Weather-Image-Classification
- Architecture: SiglipForImageClassification
- VRAM: ~200MB
- Input: 224x224 images
- Output: Weather condition with confidence score

Usage in security context:
- Weather conditions affect visibility and detection confidence
- Fog/rain may increase false positive rates
- Night+rain combinations are particularly challenging
- Weather context helps Nemotron calibrate risk assessments
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from backend.core.logging import get_logger

if TYPE_CHECKING:
    from PIL import Image

logger = get_logger(__name__)


# Weather condition labels (from model config)
WEATHER_LABELS = [
    "cloudy/overcast",
    "foggy/hazy",
    "rain/storm",  # Model has typo "strom", but we normalize
    "snow/frosty",
    "sun/clear",
]

# Simplified weather labels for context strings
WEATHER_SIMPLE_LABELS = {
    "cloudy/overcast": "cloudy",
    "foggy/hazy": "foggy",
    "rain/storm": "rainy",
    "snow/frosty": "snowy",
    "sun/clear": "clear",
}


@dataclass
class WeatherResult:
    """Result from weather classification.

    Attributes:
        condition: Weather condition label (e.g., "cloudy/overcast")
        simple_condition: Simplified condition (e.g., "cloudy")
        confidence: Classification confidence (0-1)
        all_scores: Dictionary of all class scores
    """

    condition: str
    simple_condition: str
    confidence: float
    all_scores: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "condition": self.condition,
            "simple_condition": self.simple_condition,
            "confidence": self.confidence,
            "all_scores": self.all_scores,
        }

    def to_context_string(self) -> str:
        """Generate context string for LLM prompt.

        Returns:
            Human-readable weather description for Nemotron context
        """
        conf_str = f"{self.confidence:.0%}"
        return f"Weather: {self.simple_condition} ({conf_str} confidence)"


async def load_weather_model(model_path: str) -> Any:
    """Load Weather Classification model from local path.

    This function loads the Weather-Image-Classification model using
    transformers AutoModelForImageClassification and AutoImageProcessor.

    Args:
        model_path: Local path to the downloaded model directory

    Returns:
        Dictionary containing:
            - model: The SiglipForImageClassification model instance
            - processor: The image processor for preprocessing

    Raises:
        ImportError: If transformers or torch is not installed
        RuntimeError: If model loading fails
    """
    try:
        import torch
        from transformers import AutoImageProcessor, AutoModelForImageClassification

        logger.info(f"Loading Weather Classification model from {model_path}")

        loop = asyncio.get_event_loop()

        def _load() -> dict[str, Any]:
            """Load model and processor synchronously."""
            processor = AutoImageProcessor.from_pretrained(model_path)
            model = AutoModelForImageClassification.from_pretrained(model_path)

            # Move to GPU if available
            if torch.cuda.is_available():
                model = model.cuda().half()  # Use fp16 for efficiency
                logger.info("Weather model moved to CUDA with fp16")
            else:
                logger.info("Weather model using CPU")

            # Set to eval mode
            model.eval()

            return {"model": model, "processor": processor}

        result = await loop.run_in_executor(None, _load)

        logger.info(f"Successfully loaded Weather Classification model from {model_path}")
        return result

    except ImportError as e:
        logger.warning(
            "transformers or torch package not installed. "
            "Install with: pip install transformers torch"
        )
        raise ImportError(
            "Weather classification requires transformers and torch. "
            "Install with: pip install transformers torch"
        ) from e

    except Exception as e:
        logger.error(f"Failed to load Weather Classification model from {model_path}: {e}")
        raise RuntimeError(f"Failed to load Weather Classification model: {e}") from e


async def classify_weather(
    model_dict: dict[str, Any],
    image: Image.Image,
) -> WeatherResult:
    """Classify weather condition from an image.

    Args:
        model_dict: Dictionary with 'model' and 'processor' keys from load_weather_model
        image: PIL Image (full frame from camera)

    Returns:
        WeatherResult with condition and confidence

    Raises:
        RuntimeError: If classification fails
    """
    try:
        import torch

        model = model_dict["model"]
        processor = model_dict["processor"]

        loop = asyncio.get_event_loop()

        def _classify() -> WeatherResult:
            """Run classification synchronously."""
            # Preprocess image
            inputs = processor(images=image, return_tensors="pt")

            # Move to same device as model
            if next(model.parameters()).is_cuda:
                inputs = {k: v.cuda() for k, v in inputs.items()}

            # Run inference
            with torch.no_grad():
                outputs = model(**inputs)
                logits = outputs.logits

            # Get probabilities via softmax
            probs = torch.nn.functional.softmax(logits, dim=-1)[0]

            # Get predicted class
            pred_idx = probs.argmax().item()
            confidence = probs[pred_idx].item()

            # Map to labels (handle model's id2label or use our list)
            if hasattr(model.config, "id2label") and model.config.id2label:
                raw_label = model.config.id2label.get(pred_idx, WEATHER_LABELS[pred_idx])
                # Normalize the typo "rain/strom" -> "rain/storm"
                if "strom" in raw_label:
                    raw_label = raw_label.replace("strom", "storm")
            else:
                raw_label = WEATHER_LABELS[pred_idx]

            # Build all scores dict
            all_scores = {}
            for i, label in enumerate(WEATHER_LABELS):
                score = probs[i].item()
                all_scores[label] = score

            # Get simplified label
            simple_label = WEATHER_SIMPLE_LABELS.get(raw_label, raw_label.split("/")[0])

            return WeatherResult(
                condition=raw_label,
                simple_condition=simple_label,
                confidence=confidence,
                all_scores=all_scores,
            )

        return await loop.run_in_executor(None, _classify)

    except Exception as e:
        logger.error(f"Weather classification failed: {e}")
        raise RuntimeError(f"Weather classification failed: {e}") from e


def format_weather_for_nemotron(weather_result: WeatherResult | None) -> str:
    """Format weather information for Nemotron context.

    Creates a human-readable description of weather conditions that can be
    appended to Nemotron's input context for risk analysis.

    Args:
        weather_result: WeatherResult from classify_weather, or None

    Returns:
        Formatted string describing weather conditions

    Example output:
        "Current weather: cloudy (87% confidence). Visibility may be reduced."
    """
    if weather_result is None:
        return "Weather: unknown (classification unavailable)"

    condition = weather_result.simple_condition
    confidence = weather_result.confidence

    # Add visibility/condition notes based on weather
    notes = ""
    if condition == "foggy":
        notes = " Visibility significantly reduced due to fog."
    elif condition == "rainy":
        notes = " Rain may affect visibility and detection accuracy."
    elif condition == "snowy":
        notes = " Snow conditions may affect visibility and camera image quality."
    elif condition == "cloudy":
        notes = " Overcast conditions with potentially reduced lighting."
    elif condition == "clear":
        notes = " Good visibility conditions."

    return f"Current weather: {condition} ({confidence:.0%} confidence).{notes}"


def weather_affects_visibility(weather_result: WeatherResult | None) -> bool:
    """Check if weather conditions affect visibility.

    Useful for adjusting detection confidence thresholds or flagging
    potential false positives/negatives.

    Args:
        weather_result: WeatherResult from classify_weather

    Returns:
        True if weather may significantly affect visibility/detection
    """
    if weather_result is None:
        return False

    # Conditions that significantly affect visibility
    visibility_affecting = {"foggy", "rainy", "snowy"}
    return weather_result.simple_condition in visibility_affecting


def get_visibility_factor(weather_result: WeatherResult | None) -> float:
    """Get a visibility factor based on weather conditions.

    This factor can be used to adjust confidence thresholds or
    weight detections based on weather conditions.

    Args:
        weather_result: WeatherResult from classify_weather

    Returns:
        Visibility factor from 0.0 (worst) to 1.0 (best)
            - 1.0: clear/sunny - excellent visibility
            - 0.9: cloudy - good visibility
            - 0.7: rainy - reduced visibility
            - 0.5: foggy/snowy - significantly reduced visibility
    """
    if weather_result is None:
        return 0.8  # Default to slightly reduced (unknown)

    condition = weather_result.simple_condition
    confidence = weather_result.confidence

    # Base visibility factors
    visibility_map = {
        "clear": 1.0,
        "cloudy": 0.9,
        "rainy": 0.7,
        "snowy": 0.5,
        "foggy": 0.5,
    }

    base_factor = visibility_map.get(condition, 0.8)

    # Adjust based on confidence (low confidence = less certain about visibility)
    # If confidence is low, move factor toward 0.8 (neutral)
    adjusted_factor = base_factor * confidence + 0.8 * (1 - confidence)

    return adjusted_factor
