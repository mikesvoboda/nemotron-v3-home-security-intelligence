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
        confidence_tier: Confidence tier ('definitive', 'suspected', or 'marginal')
            - definitive: violent_score >= 70% -> is_violent=True
            - suspected: violent_score 55-70% -> is_violent=False (flagged for review)
            - marginal: violent_score < 55% -> is_violent=False (excluded from prompts)
    """

    is_violent: bool
    confidence: float
    violent_score: float
    non_violent_score: float
    confidence_tier: str = "marginal"  # 'definitive', 'suspected', or 'marginal'

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "is_violent": self.is_violent,
            "confidence": self.confidence,
            "violent_score": self.violent_score,
            "non_violent_score": self.non_violent_score,
            "confidence_tier": self.confidence_tier,
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
        from pathlib import Path

        import torch
        from transformers import AutoImageProcessor, AutoModelForImageClassification

        # ViT-base inference on CPU takes 60-120+ seconds per image, holding the GIL
        # the entire time and starving the asyncio event loop (uvicorn health checks
        # time out, container goes unhealthy). Fail fast here so model_zoo marks this
        # model unavailable and the enrichment pipeline skips it gracefully on CPU hosts.
        if not torch.cuda.is_available():
            raise RuntimeError(
                "violence-detection requires CUDA — ViT-base CPU inference holds the GIL "
                "for 60-120s per image, starving the asyncio event loop. "
                "Model will be skipped on CPU-only hosts."
            )

        logger.info(f"Loading violence detection model from {model_path}")

        # Validate local model path has required files when directory exists
        # (only fires in container where /models/model-zoo/ is mounted;
        # unit tests with fake paths skip this check gracefully)
        if Path(model_path).is_dir():
            preprocessor_path = str(Path(model_path) / "preprocessor_config.json")
            if not Path(preprocessor_path).is_file():
                available = [
                    f.name for f in Path(model_path).iterdir() if not f.name.startswith(".")
                ]
                raise RuntimeError(
                    f"Violence detection model missing preprocessor_config.json at {model_path}. "
                    f"Available files: {available}. Model may need re-downloading."
                )

        loop = asyncio.get_running_loop()

        def _load() -> dict[str, Any]:
            processor = AutoImageProcessor.from_pretrained(model_path)
            model = AutoModelForImageClassification.from_pretrained(model_path)

            # Move to GPU if available, with meta-tensor guard.
            # HuggingFace models can be saved with lazy (meta) weights; calling
            # model.cuda() on them raises:
            #   NotImplementedError: Cannot copy out of meta tensor; no data!
            # Use to_empty() + load_state_dict(assign=True) to materialize first.
            try:
                import torch

                if torch.cuda.is_available():
                    if any(p.device.type == "meta" for p in model.parameters()):
                        logger.warning(
                            "Violence detection model contains meta tensors "
                            "(lazy-loaded weights). Materializing before moving to CUDA."
                        )
                        state_dict = model.state_dict()
                        model = model.to_empty(device=torch.device("cuda"))
                        model.load_state_dict(state_dict, assign=True)
                    else:
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

        loop = asyncio.get_running_loop()

        def _classify() -> ViolenceDetectionResult:
            # Preprocess the image
            inputs = processor(images=image, return_tensors="pt")

            # Move to GPU if model is on GPU
            if next(model.parameters()).is_cuda:
                inputs = {k: v.cuda() for k, v in inputs.items()}

            # Run inference
            with torch.inference_mode():
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

            # Determine tier and is_violent based on absolute thresholds
            # Tier definitions (NEM-5483):
            # - definitive: violent_score >= 70% -> is_violent=True
            # - suspected: violent_score 55-70% -> is_violent=False (flagged for review)
            # - marginal: violent_score < 55% -> is_violent=False (excluded from prompts)
            if violent_score >= 0.70:
                confidence_tier = "definitive"
                is_violent = True
            elif violent_score >= 0.55:
                confidence_tier = "suspected"
                is_violent = False  # NOT marked as violent at suspected tier
            else:
                confidence_tier = "marginal"
                is_violent = False

            # Confidence reflects the winning score
            confidence = violent_score if is_violent else non_violent_score

            return ViolenceDetectionResult(
                is_violent=is_violent,
                confidence=confidence,
                violent_score=violent_score,
                non_violent_score=non_violent_score,
                confidence_tier=confidence_tier,
            )

        # Hard timeout: the executor thread cannot be cancelled, but asyncio.wait_for
        # frees the event loop once the timeout fires so health checks and other
        # coroutines are not starved while the inference thread finishes.
        try:
            return await asyncio.wait_for(
                loop.run_in_executor(None, _classify),
                timeout=10.0,
            )
        except TimeoutError:
            logger.warning(
                "Violence classification timed out after 10s — skipping",
                extra={"model_path": str(getattr(model, "__class__", "unknown"))},
            )
            return ViolenceDetectionResult(
                is_violent=False,
                confidence=0.0,
                violent_score=0.0,
                non_violent_score=1.0,
                confidence_tier="marginal",
            )

    except Exception as e:
        logger.error("Violence classification failed", exc_info=True)
        raise RuntimeError(f"Violence classification failed: {e}") from e
