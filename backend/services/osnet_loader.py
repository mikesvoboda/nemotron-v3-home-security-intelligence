"""OSNet model loader for person re-identification embeddings.

This module provides async loading and inference for the OSNet-x0-25 model,
a lightweight person re-identification network.

OSNet (Omni-Scale Network) uses omni-scale feature learning to capture
features at multiple scales, making it effective for person re-identification
across different camera views and distances.

Model details:
- Architecture: OSNet-x0-25 (quarter-width variant)
- Input: 256x128 person crops
- Output: 512-dimensional embedding vectors
- VRAM: ~100MB (very lightweight)
- Use case: Enhanced person tracking across cameras via embedding comparison

Usage in security context:
- Generate embeddings for person detections
- Compare embeddings to track individuals across multiple cameras
- Enable "same person" alerts when unknown individual appears on multiple cameras
- Support for building person re-id database for known residents/visitors
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from backend.core.logging import get_logger

if TYPE_CHECKING:
    from PIL import Image

logger = get_logger(__name__)

# OSNet-x0-25 embedding dimension
OSNET_EMBEDDING_DIM = 512


@dataclass(slots=True)
class PersonEmbeddingResult:
    """Result from OSNet person re-identification embedding extraction.

    Attributes:
        embedding: 512-dimensional embedding vector (normalized)
        detection_id: Optional detection identifier for tracking
        confidence: Embedding quality confidence (based on input quality)
    """

    embedding: np.ndarray
    detection_id: str | None = None
    confidence: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "embedding": self.embedding.tolist(),
            "detection_id": self.detection_id,
            "confidence": self.confidence,
            "embedding_dim": len(self.embedding),
        }

    def cosine_similarity(self, other: PersonEmbeddingResult) -> float:
        """Calculate cosine similarity with another embedding.

        Args:
            other: Another PersonEmbeddingResult to compare against

        Returns:
            Cosine similarity score between -1 and 1 (higher = more similar)
        """
        # Embeddings should already be normalized, but ensure it
        norm_self = self.embedding / (np.linalg.norm(self.embedding) + 1e-8)
        norm_other = other.embedding / (np.linalg.norm(other.embedding) + 1e-8)
        return float(np.dot(norm_self, norm_other))


async def load_osnet_model(model_path: str) -> dict[str, Any]:
    """Load OSNet-x0-25 model from local path.

    This function loads the OSNet person re-identification model.
    The model uses a lightweight CNN architecture optimized for
    person re-identification tasks.

    Args:
        model_path: Local path to the model directory
                   (e.g., "/models/model-zoo/osnet-x0-25")
                   Should contain the model weights file.

    Returns:
        Dictionary containing:
            - model: The OSNet model instance
            - transform: Image transforms for preprocessing

    Raises:
        ImportError: If torch or torchvision is not installed
        RuntimeError: If model loading fails
    """
    try:
        import torch
        from torchvision import transforms

        logger.info(f"Loading OSNet-x0-25 model from {model_path}")

        loop = asyncio.get_event_loop()

        def _load() -> dict[str, Any]:
            """Load model synchronously."""
            model_dir = Path(model_path)

            # Try to load torchreid OSNet if available
            try:
                from torchreid.models import build_model

                # Build OSNet-x0-25 architecture
                model = build_model(
                    name="osnet_x0_25",
                    num_classes=1,  # We only need feature extraction
                    pretrained=False,
                )

                # Load weights
                weights_file = model_dir / "model.pth"
                if not weights_file.exists():
                    weights_file = model_dir / "osnet_x0_25_msmt17.pth"
                if not weights_file.exists():
                    # Try any .pth file in directory
                    pth_files = list(model_dir.glob("*.pth"))
                    if not pth_files:
                        msg = f"No model weights found in {model_dir}"
                        raise FileNotFoundError(msg)
                    weights_file = pth_files[0]

                state_dict = torch.load(weights_file, map_location="cpu", weights_only=True)

                # Handle 'module.' prefix from DataParallel training (NEM-3888)
                if any(k.startswith("module.") for k in state_dict):
                    state_dict = {k.replace("module.", ""): v for k, v in state_dict.items()}
                    logger.debug("Stripped 'module.' prefix from state dict keys")

                # Filter out classifier keys to avoid shape mismatch (NEM-3888)
                # Pretrained weights may have classifier.weight shape [1000, 512] (ImageNet)
                # but model is instantiated with num_classes=1, giving [1, 512]
                classifier_keys = [k for k in state_dict if k.startswith("classifier")]
                if classifier_keys:
                    for key in classifier_keys:
                        del state_dict[key]
                    logger.debug(f"Filtered out classifier keys: {classifier_keys}")

                model.load_state_dict(state_dict, strict=False)
                logger.info(f"Loaded OSNet weights from {weights_file}")

            except ImportError:
                # Fallback: load as generic feature extractor
                # This creates a simple wrapper that can load saved ONNX or TorchScript
                logger.info("torchreid not available, trying direct model load")

                weights_file = model_dir / "model.pth"
                if not weights_file.exists():
                    weights_file = model_dir / "osnet_x0_25.pth"
                if not weights_file.exists():
                    pth_files = list(model_dir.glob("*.pth"))
                    if not pth_files:
                        msg = f"No model weights found in {model_dir}"
                        raise FileNotFoundError(msg) from None
                    weights_file = pth_files[0]

                # Try loading as TorchScript
                try:
                    model = torch.jit.load(weights_file)
                    logger.info("Loaded OSNet as TorchScript model")
                except Exception as e:
                    # Try loading as state dict into a generic model
                    # This requires knowing the architecture
                    msg = (
                        "OSNet requires either torchreid package or TorchScript model. "
                        "Install torchreid: pip install torchreid"
                    )
                    raise RuntimeError(msg) from e

            # Move to GPU if available
            if torch.cuda.is_available():
                model = model.cuda()
                logger.info("OSNet model moved to CUDA")
            else:
                logger.info("OSNet model using CPU")

            # Set to eval mode
            model.eval()

            # Define image transforms for person re-id
            # Standard transforms: resize to 256x128, normalize
            transform = transforms.Compose(
                [
                    transforms.Resize((256, 128)),
                    transforms.ToTensor(),
                    transforms.Normalize(
                        mean=[0.485, 0.456, 0.406],
                        std=[0.229, 0.224, 0.225],
                    ),
                ]
            )

            return {
                "model": model,
                "transform": transform,
            }

        result = await loop.run_in_executor(None, _load)

        logger.info(f"Successfully loaded OSNet-x0-25 model from {model_path}")
        return result

    except ImportError as e:
        logger.warning(
            "torch or torchvision package not installed. "
            "Install with: pip install torch torchvision"
        )
        raise ImportError(
            "OSNet requires torch and torchvision. Install with: pip install torch torchvision"
        ) from e

    except Exception as e:
        logger.error(
            "Failed to load OSNet model",
            exc_info=True,
            extra={"model_path": model_path},
        )
        raise RuntimeError(f"Failed to load OSNet model: {e}") from e


async def extract_person_embedding(
    model_dict: dict[str, Any],
    image: Image.Image,
    detection_id: str | None = None,
) -> PersonEmbeddingResult:
    """Extract person re-identification embedding from an image crop.

    Args:
        model_dict: Dictionary containing model and transform from load_osnet_model
        image: PIL Image of person crop (should be cropped to person bbox)
        detection_id: Optional identifier for the detection

    Returns:
        PersonEmbeddingResult with 512-dimensional embedding

    Raises:
        RuntimeError: If embedding extraction fails
    """
    try:
        import torch

        model = model_dict["model"]
        transform = model_dict["transform"]

        loop = asyncio.get_event_loop()

        def _extract() -> PersonEmbeddingResult:
            """Extract embedding synchronously."""
            # Ensure RGB mode
            rgb_image = image.convert("RGB") if image.mode != "RGB" else image

            # Check if image is too small (indicates poor quality crop)
            width, height = rgb_image.size
            confidence = 1.0
            if width < 32 or height < 64:
                confidence = 0.5  # Low confidence for small crops
            elif width < 64 or height < 128:
                confidence = 0.8  # Medium confidence

            # Preprocess image
            input_tensor = transform(rgb_image).unsqueeze(0)  # Add batch dimension

            # Move to same device as model
            device = next(model.parameters()).device
            input_tensor = input_tensor.to(device)

            # Run inference
            with torch.inference_mode():
                features = model(input_tensor)

            # Handle different output formats
            if isinstance(features, tuple):
                # Some models return (features, logits)
                features = features[0]

            # Flatten if needed and convert to numpy
            embedding = features.squeeze().cpu().numpy()

            # Ensure correct dimension
            if embedding.shape[0] != OSNET_EMBEDDING_DIM:
                # Try to reshape or truncate
                if len(embedding.shape) > 1:
                    embedding = embedding.flatten()[:OSNET_EMBEDDING_DIM]
                # Pad if too short
                if embedding.shape[0] < OSNET_EMBEDDING_DIM:
                    embedding = np.pad(
                        embedding,
                        (0, OSNET_EMBEDDING_DIM - embedding.shape[0]),
                    )

            # L2 normalize the embedding
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm

            return PersonEmbeddingResult(
                embedding=embedding,
                detection_id=detection_id,
                confidence=confidence,
            )

        return await loop.run_in_executor(None, _extract)

    except Exception as e:
        logger.error("Person embedding extraction failed", exc_info=True)
        raise RuntimeError(f"Person embedding extraction failed: {e}") from e


async def extract_person_embeddings_batch(
    model_dict: dict[str, Any],
    images: list[Image.Image],
    detection_ids: list[str] | None = None,
) -> list[PersonEmbeddingResult]:
    """Extract person embeddings for multiple image crops.

    Batch processes multiple person crops for efficiency.

    Args:
        model_dict: Dictionary containing model and transform
        images: List of PIL Images (person crops)
        detection_ids: Optional list of detection identifiers

    Returns:
        List of PersonEmbeddingResult, one per input image
    """
    if not images:
        return []

    try:
        import torch

        model = model_dict["model"]
        transform = model_dict["transform"]

        loop = asyncio.get_event_loop()

        def _extract_batch() -> list[PersonEmbeddingResult]:
            """Extract embeddings for batch synchronously."""
            # Preprocess all images
            tensors = []
            confidences = []

            for img in images:
                # Ensure RGB mode
                rgb_img = img.convert("RGB") if img.mode != "RGB" else img

                # Calculate confidence based on image size
                width, height = rgb_img.size
                if width < 32 or height < 64:
                    confidences.append(0.5)
                elif width < 64 or height < 128:
                    confidences.append(0.8)
                else:
                    confidences.append(1.0)

                tensors.append(transform(rgb_img))

            # Stack into batch
            batch_tensor = torch.stack(tensors)

            # Move to same device as model
            device = next(model.parameters()).device
            batch_tensor = batch_tensor.to(device)

            # Run inference
            with torch.inference_mode():
                features = model(batch_tensor)

            # Handle different output formats
            if isinstance(features, tuple):
                features = features[0]

            # Convert to numpy
            all_embeddings = features.cpu().numpy()

            results = []
            for i, raw_embedding in enumerate(all_embeddings):
                # Flatten and ensure correct dimension
                processed = raw_embedding.flatten()
                if processed.shape[0] > OSNET_EMBEDDING_DIM:
                    processed = processed[:OSNET_EMBEDDING_DIM]
                elif processed.shape[0] < OSNET_EMBEDDING_DIM:
                    processed = np.pad(
                        processed,
                        (0, OSNET_EMBEDDING_DIM - processed.shape[0]),
                    )

                # L2 normalize
                norm = np.linalg.norm(processed)
                if norm > 0:
                    processed = processed / norm

                det_id = detection_ids[i] if detection_ids else None

                results.append(
                    PersonEmbeddingResult(
                        embedding=processed,
                        detection_id=det_id,
                        confidence=confidences[i],
                    )
                )

            return results

        return await loop.run_in_executor(None, _extract_batch)

    except Exception as e:
        logger.error("Batch person embedding extraction failed", exc_info=True)
        raise RuntimeError(f"Batch person embedding extraction failed: {e}") from e


def match_person_embeddings(
    query: PersonEmbeddingResult,
    gallery: list[PersonEmbeddingResult],
    threshold: float = 0.7,
) -> list[tuple[PersonEmbeddingResult, float]]:
    """Find matching persons in a gallery based on embedding similarity.

    Args:
        query: The query person embedding to match
        gallery: List of gallery embeddings to search
        threshold: Minimum similarity threshold for a match (default 0.7)

    Returns:
        List of (matching_result, similarity_score) tuples, sorted by similarity
    """
    matches = []

    for gallery_embedding in gallery:
        similarity = query.cosine_similarity(gallery_embedding)
        if similarity >= threshold:
            matches.append((gallery_embedding, similarity))

    # Sort by similarity (highest first)
    matches.sort(key=lambda x: x[1], reverse=True)

    return matches


def format_person_reid_context(
    matches: list[tuple[PersonEmbeddingResult, float]],
    detection_id: str,
) -> str:
    """Format person re-identification matches for prompt context.

    Args:
        matches: List of (PersonEmbeddingResult, similarity) tuples from matching
        detection_id: The detection ID being matched

    Returns:
        Formatted string for inclusion in risk analysis prompt
    """
    if not matches:
        return f"Person {detection_id}: No prior matches found (new individual)"

    lines = [f"Person {detection_id} re-identification:"]

    for match, similarity in matches[:3]:  # Top 3 matches
        match_id = match.detection_id or "unknown"
        sim_pct = f"{similarity:.0%}"
        if similarity >= 0.9:
            lines.append(f"  - HIGH CONFIDENCE match to {match_id} ({sim_pct})")
        elif similarity >= 0.8:
            lines.append(f"  - Likely same person as {match_id} ({sim_pct})")
        else:
            lines.append(f"  - Possible match to {match_id} ({sim_pct})")

    return "\n".join(lines)
