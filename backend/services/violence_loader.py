"""Violence detection model loader and classifier.

This module provides async loading and inference for the ViT-base violence detection
model (jaranohaal/vit-base-violence-detection from HuggingFace).

The model performs binary classification to detect violent vs non-violent content
in images, with 98.80% reported accuracy.

VRAM Usage: ~500MB
Model: Vision Transformer (ViT) base architecture
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from backend.core.logging import get_logger

if TYPE_CHECKING:
    from PIL import Image

logger = get_logger(__name__)


@dataclass(slots=True)
class ViolenceDetectionResult:
    """Result from violence detection classification.

    Attributes:
        is_violent: Whether violence was detected in the image
        confidence: Confidence score for the prediction (0-1)
        violent_score: Raw score for the "violent" class (0-1)
        non_violent_score: Raw score for the "non-violent" class (0-1)
    """

    is_violent: bool
    confidence: float
    violent_score: float
    non_violent_score: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "is_violent": self.is_violent,
            "confidence": self.confidence,
            "violent_score": self.violent_score,
            "non_violent_score": self.non_violent_score,
        }


async def load_violence_model(model_path: str) -> Any:
    """Load the ViT violence detection model from local path or HuggingFace.

    This function loads the vision transformer model for binary violence
    classification.

    Args:
        model_path: Local path to model directory or HuggingFace model ID
                   (e.g., "/export/ai_models/model-zoo/violence-detection")

    Returns:
        Dictionary containing:
            - model: The ViT model instance
            - processor: The image processor for preprocessing

    Raises:
        ImportError: If transformers is not installed
        RuntimeError: If model loading fails
    """
    try:
        from transformers import AutoImageProcessor, AutoModelForImageClassification

        logger.info(f"Loading violence detection model from {model_path}")

        loop = asyncio.get_event_loop()

        def _load() -> dict[str, Any]:
            processor = AutoImageProcessor.from_pretrained(model_path)
            model = AutoModelForImageClassification.from_pretrained(model_path)

            # Move to GPU if available
            try:
                import torch

                if torch.cuda.is_available():
                    model = model.cuda()
                    model.eval()
                    logger.info("Violence detection model moved to CUDA")
                else:
                    model.eval()
            except ImportError:
                model.eval()

            return {"model": model, "processor": processor}

        result = await loop.run_in_executor(None, _load)

        logger.info(f"Successfully loaded violence detection model from {model_path}")
        return result

    except ImportError as e:
        logger.warning("transformers package not installed. Install with: pip install transformers")
        raise ImportError(
            "transformers package required for violence detection. "
            "Install with: pip install transformers"
        ) from e

    except Exception as e:
        logger.error(
            "Failed to load violence detection model",
            exc_info=True,
            extra={"model_path": model_path},
        )
        raise RuntimeError(f"Failed to load violence detection model: {e}") from e


async def classify_violence(
    model_data: dict[str, Any],
    image: Image.Image,
) -> ViolenceDetectionResult:
    """Classify whether an image contains violence.

    Args:
        model_data: Dictionary containing 'model' and 'processor' from load_violence_model
        image: PIL Image to classify

    Returns:
        ViolenceDetectionResult with classification results

    Raises:
        RuntimeError: If classification fails
    """
    try:
        import torch

        model = model_data["model"]
        processor = model_data["processor"]

        loop = asyncio.get_event_loop()

        def _classify() -> ViolenceDetectionResult:
            # Preprocess the image
            inputs = processor(images=image, return_tensors="pt")

            # Move to GPU if model is on GPU
            if next(model.parameters()).is_cuda:
                inputs = {k: v.cuda() for k, v in inputs.items()}

            # Run inference
            with torch.no_grad():
                outputs = model(**inputs)
                logits = outputs.logits

            # Apply softmax to get probabilities
            probs = torch.nn.functional.softmax(logits, dim=-1)

            # Get class labels from model config
            # Model typically has id2label mapping: {0: "non-violent", 1: "violent"}
            # or similar - we need to check the config
            id2label = model.config.id2label if hasattr(model.config, "id2label") else None

            # Determine which index corresponds to "violent"
            violent_idx = 1
            non_violent_idx = 0

            if id2label:
                for idx, label in id2label.items():
                    label_lower = label.lower()
                    if "violent" in label_lower and "non" not in label_lower:
                        violent_idx = int(idx)
                    elif "non" in label_lower or "safe" in label_lower:
                        non_violent_idx = int(idx)

            # Extract scores
            probs_list = probs[0].cpu().tolist()

            # Handle different number of classes
            if len(probs_list) >= 2:
                violent_score = probs_list[violent_idx]
                non_violent_score = probs_list[non_violent_idx]
            else:
                # Binary with single output
                violent_score = probs_list[0]
                non_violent_score = 1.0 - violent_score

            # Determine prediction
            is_violent = violent_score > non_violent_score
            confidence = violent_score if is_violent else non_violent_score

            return ViolenceDetectionResult(
                is_violent=is_violent,
                confidence=confidence,
                violent_score=violent_score,
                non_violent_score=non_violent_score,
            )

        return await loop.run_in_executor(None, _classify)

    except Exception as e:
        logger.error("Violence classification failed", exc_info=True)
        raise RuntimeError(f"Violence classification failed: {e}") from e
