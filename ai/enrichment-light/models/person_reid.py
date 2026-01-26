"""OSNet-x0.25 Person Re-Identification Model.

This module provides the PersonReID class for generating person embeddings
that can be used to track individuals across cameras and time.

Features:
- Generates 512-dimensional normalized embeddings
- Cosine similarity computation for person matching
- Configurable matching threshold
- Embedding hash for quick lookup

Reference:
- Model: torchreid/osnet_x0_25
- Paper: Omni-Scale Feature Learning for Person Re-Identification
- HuggingFace: Not directly available, uses torchreid library or direct weights

VRAM Usage: ~100MB
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Any

import numpy as np
import torch
from PIL import Image

logger = logging.getLogger(__name__)

# OSNet-x0.25 input dimensions
OSNET_INPUT_HEIGHT = 256
OSNET_INPUT_WIDTH = 128

# Embedding dimension for OSNet-x0.25
EMBEDDING_DIMENSION = 512

# ImageNet normalization constants
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]

# Default similarity threshold for same-person matching
DEFAULT_SIMILARITY_THRESHOLD = 0.7


@dataclass
class ReIDResult:
    """Result from person re-identification embedding extraction.

    Attributes:
        embedding: 512-dimensional normalized embedding vector
        embedding_hash: First 16 characters of SHA-256 hash for quick lookup
    """

    embedding: list[float]
    embedding_hash: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "embedding": self.embedding,
            "embedding_hash": self.embedding_hash,
        }


class PersonReID:
    """OSNet-x0.25 person re-identification model wrapper.

    This model generates 512-dimensional embeddings for person crops that can
    be used to track individuals across cameras and time. Embeddings are
    normalized to unit length for cosine similarity computation.

    The model is optimized for small VRAM footprint (~100MB) while maintaining
    good re-identification accuracy.

    Example usage:
        >>> reid = PersonReID("/models/osnet-reid")
        >>> reid.load_model()
        >>> result = reid.extract_embedding(person_crop_image)
        >>> print(f"Embedding hash: {result.embedding_hash}")

        # Compare two persons
        >>> sim = reid.compute_similarity(emb1, emb2)
        >>> is_same = reid.is_same_person(emb1, emb2, threshold=0.7)
    """

    def __init__(self, model_path: str | None = None, device: str = "cuda:0"):
        """Initialize person re-identification model.

        Args:
            model_path: Path to OSNet model weights file (.pth) or directory.
                       If None, will attempt to use torchreid pretrained weights.
            device: Device to run inference on (default: "cuda:0")
        """
        self.model_path = model_path
        self.device = device
        self.model: Any = None
        self._transform: Any = None

        logger.info(f"Initializing PersonReID from {self.model_path or 'pretrained'}")

    def load_model(self) -> PersonReID:
        """Load the OSNet-x0.25 model into memory.

        Attempts to load using torchreid library first, then falls back to
        direct weight loading if torchreid is not available.

        Returns:
            Self for method chaining.

        Raises:
            ImportError: If neither torchreid nor weights file is available.
            FileNotFoundError: If specified model_path doesn't exist.
        """
        from torchvision import transforms

        logger.info("Loading OSNet-x0.25 model for person re-identification...")

        # Try to use torchreid if available
        try:
            self._load_with_torchreid()
        except ImportError:
            logger.info("torchreid not available, attempting direct weight loading")
            self._load_direct_weights()

        # Move to device
        if "cuda" in self.device and torch.cuda.is_available():
            self.model = self.model.to(self.device)
            # Use half precision for efficiency
            self.model = self.model.half()
            logger.info(f"PersonReID loaded on {self.device} with fp16")
        else:
            self.device = "cpu"
            logger.info("PersonReID using CPU")

        self.model.eval()

        # Create preprocessing transform
        self._transform = transforms.Compose(
            [
                transforms.Resize((OSNET_INPUT_HEIGHT, OSNET_INPUT_WIDTH)),
                transforms.ToTensor(),
                transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
            ]
        )

        logger.info("PersonReID loaded successfully")
        return self

    def _load_with_torchreid(self) -> None:
        """Load model using torchreid library."""
        import torchreid

        # Build model architecture
        self.model = torchreid.models.build_model(
            name="osnet_x0_25",
            num_classes=1,  # Not used for feature extraction
            pretrained=self.model_path is None,
        )

        # Load custom weights if provided
        if self.model_path:
            torchreid.utils.load_pretrained_weights(self.model, self.model_path)
            logger.info(f"Loaded weights from {self.model_path}")
        else:
            logger.info("Using pretrained torchreid weights")

    def _load_direct_weights(self) -> None:
        """Load model weights directly without torchreid.

        This is a fallback method when torchreid is not installed but
        we have the weights file.
        """
        if not self.model_path:
            raise ImportError(
                "torchreid not available and no model_path specified. "
                "Install torchreid or provide a weights file path."
            )

        # Load the state dict directly
        # This assumes the weights are in the standard OSNet format
        state_dict = torch.load(self.model_path, map_location="cpu", weights_only=True)

        # Try to infer model architecture from state dict
        # This is a simplified fallback - full implementation would
        # include the OSNet architecture definition
        logger.warning(
            "Direct weight loading without torchreid is limited. "
            "Consider installing torchreid for full functionality."
        )
        self.model = self._create_osnet_x0_25()
        self.model.load_state_dict(state_dict)

    def _create_osnet_x0_25(self) -> torch.nn.Module:
        """Create OSNet-x0.25 architecture.

        This is a simplified placeholder. In production, the full OSNet
        architecture should be implemented or torchreid should be used.

        Returns:
            A torch Module that can be used for feature extraction.

        Raises:
            ImportError: Always raises, directing users to install torchreid.
        """
        raise ImportError(
            "Direct OSNet architecture creation is not supported. "
            "Please install torchreid: pip install torchreid"
        )

    def _preprocess(self, image: Image.Image | np.ndarray) -> torch.Tensor:
        """Preprocess image for model input.

        Args:
            image: PIL Image or numpy array of person crop.

        Returns:
            Preprocessed tensor ready for model input.
        """
        if isinstance(image, np.ndarray):
            image = Image.fromarray(image)

        # Ensure RGB mode
        if image.mode != "RGB":
            image = image.convert("RGB")

        # Apply transforms
        img_tensor: torch.Tensor = self._transform(image)

        # Add batch dimension and move to device with correct dtype
        model_dtype = next(self.model.parameters()).dtype
        return img_tensor.unsqueeze(0).to(self.device, model_dtype)

    def extract_embedding(self, person_crop: Image.Image | np.ndarray) -> ReIDResult:
        """Extract 512-dimensional embedding for a person crop.

        The embedding is normalized to unit length for cosine similarity
        computation. A hash is also generated for quick lookup.

        Args:
            person_crop: PIL Image or numpy array of the person crop.
                        Should be the bounding box region containing the person.

        Returns:
            ReIDResult containing the embedding and hash.

        Raises:
            RuntimeError: If model is not loaded.
        """
        if self.model is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        img_tensor = self._preprocess(person_crop)

        with torch.inference_mode():
            # Extract features
            embedding = self.model(img_tensor)

            # Handle different output formats
            if isinstance(embedding, tuple):
                # Some models return (global_feat, local_feat)
                embedding = embedding[0]

            # Move to CPU and convert to numpy
            embedding = embedding.cpu().float().numpy().flatten()

        # L2 normalize the embedding
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm

        # Validate embedding dimension
        if len(embedding) != EMBEDDING_DIMENSION:
            logger.warning(
                f"Unexpected embedding dimension: {len(embedding)}, expected {EMBEDDING_DIMENSION}"
            )

        # Create hash for quick lookup
        embedding_hash = hashlib.sha256(embedding.tobytes()).hexdigest()[:16]

        return ReIDResult(
            embedding=embedding.tolist(),
            embedding_hash=embedding_hash,
        )

    @staticmethod
    def compute_similarity(emb1: list[float], emb2: list[float]) -> float:
        """Compute cosine similarity between two embeddings.

        Since embeddings are already L2 normalized, cosine similarity
        is simply the dot product.

        Args:
            emb1: First embedding vector (512-dim).
            emb2: Second embedding vector (512-dim).

        Returns:
            Cosine similarity in range [-1, 1]. Higher values indicate
            more similar embeddings.
        """
        a = np.array(emb1)
        b = np.array(emb2)

        # Embeddings should already be normalized, but normalize again
        # for robustness
        a_norm = np.linalg.norm(a)
        b_norm = np.linalg.norm(b)

        if a_norm == 0 or b_norm == 0:
            return 0.0

        return float(np.dot(a, b) / (a_norm * b_norm))

    @staticmethod
    def is_same_person(
        emb1: list[float],
        emb2: list[float],
        threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    ) -> bool:
        """Determine if two embeddings are likely the same person.

        Args:
            emb1: First embedding vector (512-dim).
            emb2: Second embedding vector (512-dim).
            threshold: Similarity threshold for matching (default: 0.7).
                      Higher threshold = stricter matching.

        Returns:
            True if similarity exceeds threshold, indicating likely same person.
        """
        similarity = PersonReID.compute_similarity(emb1, emb2)
        return similarity > threshold

    def unload(self) -> None:
        """Unload the model from memory.

        Useful for freeing VRAM when the model is no longer needed.
        """
        if self.model is not None:
            del self.model
            self.model = None

        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        logger.info("PersonReID model unloaded")


def load_person_reid(model_path: str | None = None) -> PersonReID:
    """Factory function for model registry.

    Creates and loads a PersonReID model. This function is intended
    to be used with the OnDemandModelManager.

    Args:
        model_path: Optional path to model weights.

    Returns:
        Loaded PersonReID model instance.
    """
    reid = PersonReID(model_path)
    reid.load_model()
    return reid
