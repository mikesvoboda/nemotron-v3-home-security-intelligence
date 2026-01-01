"""CLIP model loader for re-identification embeddings.

This module provides async loading of CLIP ViT-L models for generating
embeddings used in entity re-identification across cameras.

The CLIP model generates 768-dimensional embeddings that can be compared
using cosine similarity to match entities across different camera views.
"""

from __future__ import annotations

import asyncio
from typing import Any

from backend.core.logging import get_logger

logger = get_logger(__name__)


async def load_clip_model(model_path: str) -> Any:
    """Load a CLIP model from HuggingFace.

    This function loads the CLIP ViT-L model for generating embeddings
    used in entity re-identification.

    Args:
        model_path: HuggingFace model path (e.g., "openai/clip-vit-large-patch14")

    Returns:
        Dictionary containing:
            - model: The CLIP model instance
            - processor: The CLIP processor for image preprocessing

    Raises:
        ImportError: If transformers is not installed
        RuntimeError: If model loading fails
    """
    try:
        from transformers import CLIPModel, CLIPProcessor

        logger.info(f"Loading CLIP model from {model_path}")

        loop = asyncio.get_event_loop()

        # Load model and processor in thread pool to avoid blocking
        def _load() -> dict[str, Any]:
            processor = CLIPProcessor.from_pretrained(model_path)
            model = CLIPModel.from_pretrained(model_path)

            # Move to GPU if available
            try:
                import torch

                if torch.cuda.is_available():
                    model = model.cuda()
                    logger.info("CLIP model moved to CUDA")
            except ImportError:
                pass

            return {"model": model, "processor": processor}

        result = await loop.run_in_executor(None, _load)

        logger.info(f"Successfully loaded CLIP model from {model_path}")
        return result

    except ImportError as e:
        logger.warning("transformers package not installed. Install with: pip install transformers")
        raise ImportError(
            "transformers package required for CLIP. Install with: pip install transformers"
        ) from e

    except Exception as e:
        logger.error(f"Failed to load CLIP model from {model_path}: {e}")
        raise RuntimeError(f"Failed to load CLIP model: {e}") from e
