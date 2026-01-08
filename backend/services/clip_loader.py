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
from backend.services.model_loader_base import ModelLoaderBase

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
                pass  # torch not installed, model will run on CPU

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
        logger.error("Failed to load CLIP model", exc_info=True, extra={"model_path": model_path})
        raise RuntimeError(f"Failed to load CLIP model: {e}") from e


class CLIPLoader(ModelLoaderBase[dict[str, Any]]):
    """Class-based CLIP model loader implementing ModelLoaderBase.

    This class provides a standardized interface for loading CLIP models
    following the Model Loader Base pattern. It wraps the functional
    load_clip_model implementation.

    Attributes:
        model_path: Path to the model (HuggingFace repo or local path)
        _model: Loaded model dictionary (model + processor)

    Example:
        loader = CLIPLoader("openai/clip-vit-large-patch14")
        model = await loader.load("cuda")
        # Use model...
        await loader.unload()
    """

    def __init__(self, model_path: str) -> None:
        """Initialize CLIP loader.

        Args:
            model_path: HuggingFace model path or local path
        """
        self.model_path = model_path
        self._model: dict[str, Any] | None = None

    @property
    def model_name(self) -> str:
        """Get the unique identifier for this model."""
        return "clip-vit-l"

    @property
    def vram_mb(self) -> int:
        """Get the estimated VRAM usage in megabytes."""
        return 800  # CLIP ViT-L uses ~800MB

    async def load(self, device: str = "cuda") -> dict[str, Any]:
        """Load the CLIP model.

        Args:
            device: Target device (default: "cuda")

        Returns:
            Dictionary with 'model' and 'processor' keys

        Raises:
            ImportError: If transformers is not installed
            RuntimeError: If model loading fails
        """
        self._model = await load_clip_model(self.model_path)

        # Move to specific device if requested
        if device != "cuda" and "model" in self._model:
            try:
                import torch  # noqa: F401

                model = self._model["model"]
                if device.startswith("cuda:"):
                    model = model.cuda(int(device.split(":")[1]))
                elif device == "cpu":
                    model = model.cpu()

                self._model["model"] = model
            except (ImportError, ValueError):
                pass  # Keep model on default device

        return self._model

    async def unload(self) -> None:
        """Unload the CLIP model and free GPU memory."""
        if self._model is not None:
            # Delete model references
            if "model" in self._model:
                del self._model["model"]
            if "processor" in self._model:
                del self._model["processor"]

            self._model = None

            # Clear CUDA cache
            try:
                import torch

                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except ImportError:
                pass
