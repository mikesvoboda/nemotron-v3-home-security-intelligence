"""Abstract base class for model loaders.

This module provides the abstract base class that all model loaders in the
Model Zoo must inherit from. This ensures a consistent interface across all
14+ model loaders for loading, unloading, and resource management.

All model loaders must implement:
- model_name: Unique identifier for the model
- vram_mb: Estimated VRAM usage in megabytes
- load(device): Async method to load the model
- unload(): Async method to unload the model and free resources

Example usage:
    class CLIPLoader(ModelLoaderBase[dict]):
        @property
        def model_name(self) -> str:
            return "clip-vit-l"

        @property
        def vram_mb(self) -> int:
            return 800

        async def load(self, device: str = "cuda") -> dict:
            # Load model logic here
            return {"model": model, "processor": processor}

        async def unload(self) -> None:
            # Cleanup logic here
            del self._model
            torch.cuda.empty_cache()
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

# Generic type for the model instance
T = TypeVar("T")


class ModelLoaderBase(ABC, Generic[T]):  # noqa: UP046
    """Abstract base class for model loaders in the Model Zoo.

    This class defines the required interface that all model loaders must
    implement. It uses Python's ABC (Abstract Base Class) mechanism to
    enforce that subclasses provide implementations for all required methods.

    Type Parameters:
        T: The type of the model instance returned by load()
           (e.g., dict, object, tuple, etc.)

    Required Properties:
        model_name: Unique identifier for the model (e.g., "clip-vit-l")
        vram_mb: Estimated VRAM usage in megabytes

    Required Methods:
        load(device): Load the model and return the model instance
        unload(): Unload the model and free GPU memory
    """

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Get the unique identifier for this model.

        This name is used in the Model Zoo registry to identify and load
        the model. It should be unique across all models.

        Returns:
            Unique model identifier (e.g., "clip-vit-l", "yolo11-face")

        Example:
            @property
            def model_name(self) -> str:
                return "clip-vit-l"
        """
        ...

    @property
    @abstractmethod
    def vram_mb(self) -> int:
        """Get the estimated VRAM usage in megabytes.

        This is used by the Model Zoo to manage VRAM budget and decide
        whether a model can be loaded given available GPU memory.

        Returns:
            Estimated VRAM usage in megabytes

        Example:
            @property
            def vram_mb(self) -> int:
                return 800  # 800 MB for CLIP ViT-L
        """
        ...

    @abstractmethod
    async def load(self, device: str = "cuda") -> T:
        """Load the model and return the model instance.

        This method is responsible for:
        1. Loading model weights from disk or HuggingFace
        2. Moving the model to the specified device (GPU/CPU)
        3. Setting the model to evaluation mode
        4. Returning the loaded model instance

        Args:
            device: Target device for the model. Defaults to "cuda".
                   Supports "cuda", "cpu", "cuda:0", "cuda:1", etc.

        Returns:
            The loaded model instance (type varies by model)

        Raises:
            ImportError: If required packages are not installed
            RuntimeError: If model loading fails

        Example:
            async def load(self, device: str = "cuda") -> dict:
                from transformers import CLIPModel, CLIPProcessor

                processor = CLIPProcessor.from_pretrained(self.model_path)
                model = CLIPModel.from_pretrained(self.model_path)

                if device.startswith("cuda"):
                    model = model.cuda()

                return {"model": model, "processor": processor}
        """
        ...

    @abstractmethod
    async def unload(self) -> None:
        """Unload the model and free GPU memory.

        This method is responsible for:
        1. Deleting model references
        2. Clearing CUDA cache (if applicable)
        3. Freeing any other resources held by the model

        This is called by the Model Zoo after the model is no longer needed
        to ensure GPU memory is freed for other models.

        Example:
            async def unload(self) -> None:
                if self._model is not None:
                    del self._model
                    self._model = None

                try:
                    import torch
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                except ImportError:
                    pass
        """
        ...
