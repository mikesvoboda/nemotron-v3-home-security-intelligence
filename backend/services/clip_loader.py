"""SigLIP 2 model loader for re-identification embeddings.

This module provides async loading of SigLIP 2 Base models (replacing CLIP ViT-L)
for generating embeddings used in entity re-identification across cameras.

SigLIP 2 Base generates 768-dimensional embeddings (same as CLIP ViT-L) that
can be compared using cosine similarity to match entities across different
camera views. It uses 178MB FP16 vs CLIP's 1.2GB, saving 1,035MB VRAM.
"""

from __future__ import annotations

import asyncio
from typing import Any, override

from backend.core.logging import get_logger
from backend.services.model_loader_base import ModelLoaderBase

logger = get_logger(__name__)


async def load_clip_model(model_path: str) -> Any:
    """Load a SigLIP 2 model for embedding generation.

    This function loads the SigLIP 2 Base model for generating embeddings
    used in entity re-identification. Function name kept as load_clip_model
    for backward compatibility with model_zoo.py.

    Args:
        model_path: Local path to SigLIP 2 model directory

    Returns:
        Dictionary containing:
            - model: The SigLIP 2 model instance
            - processor: The SigLIP 2 processor for image preprocessing

    Raises:
        ImportError: If transformers is not installed
        RuntimeError: If model loading fails
    """
    try:
        from transformers import AutoModel, AutoProcessor

        logger.info(f"Loading SigLIP 2 model from {model_path}")

        loop = asyncio.get_running_loop()

        # Load model and processor in thread pool to avoid blocking
        def _load() -> dict[str, Any]:
            processor = AutoProcessor.from_pretrained(model_path)
            model = AutoModel.from_pretrained(model_path)

            # Set model to evaluation mode for deterministic inference
            model.eval()

            # Move to GPU if available
            try:
                import torch

                if torch.cuda.is_available():
                    model = model.cuda()
                    logger.info("SigLIP 2 model moved to CUDA")
            except ImportError:
                pass

            return {"model": model, "processor": processor}

        result = await loop.run_in_executor(None, _load)

        logger.info(f"Successfully loaded SigLIP 2 model from {model_path}")
        return result

    except ImportError as e:
        logger.warning("transformers package not installed. Install with: pip install transformers")
        raise ImportError(
            "transformers package required for SigLIP 2. Install with: pip install transformers"
        ) from e

    except Exception as e:
        logger.error(
            "Failed to load SigLIP 2 model", exc_info=True, extra={"model_path": model_path}
        )
        raise RuntimeError(f"Failed to load SigLIP 2 model: {e}") from e


class CLIPLoader(ModelLoaderBase[dict[str, Any]]):
    """Class-based SigLIP 2 model loader implementing ModelLoaderBase.

    This class provides a standardized interface for loading SigLIP 2 models
    (replacing CLIP ViT-L) following the Model Loader Base pattern.

    Attributes:
        model_path: Path to the model (local path)
        _model: Loaded model dictionary (model + processor)

    Example:
        loader = CLIPLoader("/models/model-zoo/siglip2-base-patch16-224")
        model = await loader.load("cuda")
        # Use model...
        await loader.unload()
    """

    def __init__(self, model_path: str) -> None:
        """Initialize SigLIP 2 loader.

        Args:
            model_path: Local model path
        """
        self.model_path = model_path
        self._model: dict[str, Any] | None = None

    @property
    @override
    def model_name(self) -> str:
        """Get the unique identifier for this model."""
        return "siglip2-base-patch16-224"

    @property
    @override
    def vram_mb(self) -> int:
        """Get the estimated VRAM usage in megabytes."""
        return 200  # SigLIP 2 Base FP16 uses ~200MB (vs CLIP ViT-L 800MB)

    @override
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
                # torch not installed or invalid device spec - keep model on default device.
                # Model will still function, just potentially on different device than requested.
                # See: NEM-2540 for rationale
                pass

        return self._model

    @override
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
                # torch not installed - no CUDA cache to clear.
                # Model unload completes successfully without CUDA cleanup.
                # See: NEM-2540 for rationale
                pass
