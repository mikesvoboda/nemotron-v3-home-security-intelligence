"""OSNet model loader for person re-identification embeddings.

This module provides async loading and inference for OSNet-AIN x1.0,
a person re-identification network with Attention-based Instance Normalization.

Upgraded from OSNet-x0.25 to OSNet-AIN x1.0 for 4x better re-identification
accuracy (NEM-5562). Uses MSMT17 domain-generalization training for better
cross-domain generalization to unseen cameras.

Model details:
- Architecture: OSNet-AIN x1.0 (full-width with attention instance norm)
- Input: 256x128 person crops
- Output: 512-dimensional embedding vectors
- VRAM: ~100MB
- Use case: Enhanced person tracking across cameras via embedding comparison

Usage in security context:
- Generate embeddings for person detections
- Compare embeddings to track individuals across multiple cameras
- Enable "same person" alerts when unknown individual appears on multiple cameras
- Support for building person re-id database for known residents/visitors
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib
import sys
import types
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from backend.core.logging import get_logger

if TYPE_CHECKING:
    from PIL import Image

logger = get_logger(__name__)

# OSNet-AIN x1.0 embedding dimension
OSNET_EMBEDDING_DIM = 512

# The zoo name of the row that owns these weights (models.yml is the single
# source: weights file + sha256 pin + belt, all read from it).
OSNET_ZOO_NAME = "osnet-ain-x1-0"


def _osnet_zoo_row() -> dict[str, Any]:
    """The osnet row of models.yml, read directly (NOT via model_zoo: the
    zoo imports THIS module, so a module-level import would be a cycle —
    same reason get_reid_handle imports lazily)."""
    import yaml

    models_yml = Path(__file__).resolve().parents[2] / "models.yml"
    entries: list[dict[str, Any]] = yaml.safe_load(models_yml.read_text())["models"]
    for entry in entries:
        if entry.get("name") == OSNET_ZOO_NAME:
            return entry
    return {}


def osnet_model_id() -> str:
    """THE belt string for every OSNet person vector (F11, ledger item 20).

    Grammar is the face loader's (``role@weightsfile@sha[:12]``) and the
    value is DERIVED from the models.yml row — never a literal — so the
    backend handle, the Triton ``reid`` producer's payload labels, and the
    safe-extract payloads all stamp ONE string (B5b: "one space" is
    mechanical). A weights swap changes the row's sha, which changes every
    future belt at once; old rows then compare against nothing and honest
    re-enroll is the only answer.
    """
    row = _osnet_zoo_row()
    weights_file = str(row.get("runtime_file") or "osnet_ain_x1_0_msmt17.pth")
    stem = Path(weights_file).stem
    sha = str(row.get("sha256") or "")
    return f"{OSNET_ZOO_NAME}@{stem}@{sha[:12]}" if sha else f"{OSNET_ZOO_NAME}@{stem}"


def _model_id(role: str, weights: Path, expected_sha256: str | None) -> str:
    """Load-time belt (face _model_id grammar, verbatim): the id names the
    ACTUAL weights file plus the pin that was satisfied loading it. With the
    row's sha this equals osnet_model_id(); a hand-deployed different file
    gets its OWN id — which is exactly what a different space means."""
    base = f"{role}@{weights.stem}"
    return f"{base}@{expected_sha256[:12]}" if expected_sha256 else base


def _ensure_tensorboard_importable() -> None:
    """Pre-register a minimal torch.utils.tensorboard stub (B2 hazard).

    torchreid's PACKAGE chain imports torch.utils.tensorboard at import
    time (engine.py -> SummaryWriter); that module needs the tensorboard
    package, which this project does not ship. Without the stub every env
    without tensorboard falls silently into the TorchScript branch of
    load_osnet_model — and since nobody ships a TorchScript .pth, the REAL
    weights become a RuntimeError and the whole store answers
    "unavailable" in the field.

    SummaryWriter is trainer-only (never inference), so the stub is inert
    by construction. If the real module IS importable we never shadow it.
    """
    if "torch.utils.tensorboard" in sys.modules:
        return
    try:
        importlib.import_module("torch.utils.tensorboard")
        return
    except Exception as e:
        logger.debug("torch.utils.tensorboard not importable (%s); stubbing", e)
    stub = types.ModuleType("torch.utils.tensorboard")

    class SummaryWriter:  # trainer-only surface, bounded on purpose
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def add_scalar(self, *args: Any, **kwargs: Any) -> None:
            pass

        def flush(self) -> None:
            pass

        def close(self) -> None:
            pass

    stub.SummaryWriter = SummaryWriter  # type: ignore[attr-defined]
    sys.modules["torch.utils.tensorboard"] = stub
    logger.debug("Registered inert torch.utils.tensorboard stub for torchreid")


def _import_build_model() -> Any:
    """torchreid's build_model across package layouts.

    This installed torchreid keeps models under torchreid.reid.models —
    ``from torchreid.models import ...`` (the spelling that shipped) fails
    on it, which is only visible without mocks. Try nested, then flat.
    """
    for spelling in ("torchreid.reid.models", "torchreid.models"):
        try:
            mod = importlib.import_module(spelling)
        except Exception:  # noqa: S112 - deliberate layout probe: next spelling
            continue
        builder = getattr(mod, "build_model", None)
        if builder is not None:
            return builder
    raise ImportError("torchreid build_model is not importable")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _enforce_embedding_dim(embedding: np.ndarray) -> np.ndarray:
    """D-5: a 512-d vector or a loud refusal — never a coerced one.

    The retired behaviour flattened, TRUNCATED and PADDED to 512, which
    turned a wrong checkpoint (or a model swap nobody announced) into a
    plausible-looking vector with no trail — the exact silent-drift class
    the ledger doctrine forbids. A real OSNet-AIN x1.0 run gives 512, so
    anything else means the weights are not what the belt claims.
    """
    flat = embedding.flatten() if embedding.ndim > 1 else embedding
    if flat.shape[0] != OSNET_EMBEDDING_DIM:
        msg = (
            f"OSNet produced a {flat.shape[0]}-dim feature vector, expected "
            f"{OSNET_EMBEDDING_DIM} — the loaded weights are not the pinned "
            "osnet_ain_x1_0 build. Refusing to pad/truncate into a "
            "plausible-looking vector (D-5)."
        )
        logger.error(msg)
        raise RuntimeError(msg)
    return flat


def get_reid_handle() -> dict[str, Any] | None:
    """The resident OSNet handle, or None — a membership read, NEVER a load
    trigger (the face get_face_leg_handles pattern).

    The row is ``enabled: true``, so the BACKEND_MODEL_PRELOAD sweep loads
    it at boot; a deploy without the weights (or with preload off, as in
    CPU/sandbox) has NO entry — and the leg/enrollment answer unavailable,
    which is the honest degrade, not a silent stub.

    The import is lazy because model_zoo imports this module: a module-level
    import would be a cycle.
    """
    from backend.services.model_zoo import get_model_manager

    loaded = get_model_manager()._loaded_models
    handle = loaded.get(OSNET_ZOO_NAME)
    if handle is None or not isinstance(handle, dict) or "model" not in handle:
        return None
    return handle


@dataclass(slots=True)
class PersonEmbeddingResult:
    """Result from OSNet person re-identification embedding extraction.

    Attributes:
        embedding: 512-dimensional embedding vector (normalized)
        detection_id: Optional detection identifier for tracking
        confidence: Embedding quality confidence (based on input quality)
        model_id: Which weights computed the vector (F11 provenance). None
            is legal only pre-extraction — a caller that STORES the vector
            must carry a real id, so the belt is threaded by whoever holds
            the handle, not defaulted here (a default would launder).
    """

    embedding: np.ndarray
    detection_id: str | None = None
    confidence: float = 1.0
    model_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "embedding": self.embedding.tolist(),
            "detection_id": self.detection_id,
            "confidence": self.confidence,
            "embedding_dim": len(self.embedding),
            "model_id": self.model_id,
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


async def load_osnet_model(model_path: str, expected_sha256: str | None = None) -> dict[str, Any]:
    """Load OSNet-AIN x1.0 model from a weights FILE or a model directory.

    This function loads the OSNet-AIN x1.0 person re-identification model.
    The model uses Attention-based Instance Normalization for better
    cross-domain generalization.

    Pinning (F12, ledger item 20 — the face loaders' shape): when the zoo
    row pins ``expected_sha256``, the file's SHA-256 is computed and checked
    BEFORE ``torch.load`` runs. Wrong bytes are the same answer as no bytes:
    the load raises and nothing is deserialized — a checkpoint that isn't
    the pinned one never becomes a model, let alone a stored vector.

    ``model_path`` may be the weights file itself (what the zoo resolves for
    a row with ``runtime_file``) or the directory containing it (hand
    deploys, tests). The returned ``model_id`` names the ACTUAL file loaded
    plus the satisfied pin, so a hand-deployed different weights file gets
    its own id — a different space, honestly labeled.

    Security (NEM-4501): Model path is validated to prevent path traversal.
    Security (NEM-4519): Model weights are loaded with weights_only=True
    to prevent arbitrary code execution. Key mismatches are validated.

    Args:
        model_path: Path to the weights file or to the model directory
                   (e.g., "/models/model-zoo/osnet-ain-x1-0")
        expected_sha256: The zoo row's pinned SHA-256; enforced pre-load.

    Returns:
        Dictionary containing:
            - model: The OSNet model instance
            - transform: Image transforms for preprocessing
            - model_id: The F11 belt (``osnet-ain-x1-0@<file>@<sha[:12]>``)
            - embedding_dim: 512

    Raises:
        ImportError: If torch or torchvision is not installed
        RuntimeError: If model loading fails, path validation fails, or the
            weights fail the sha256 pin
    """
    try:
        import torch
        from torchvision import transforms

        from backend.core.security import PathSecurityError, validate_model_path

        # Validate model path to prevent path traversal (NEM-4501)
        # Note: must_exist=False because the downstream code checks for file existence
        # and provides more specific error messages
        try:
            validate_model_path(
                model_path,
                allowed_extensions=frozenset(),  # Directory, no extension check
                must_exist=False,
            )
        except PathSecurityError as e:
            raise RuntimeError(f"Invalid model path: {e}") from e

        logger.info(f"Loading OSNet-AIN x1.0 model from {model_path}")

        loop = asyncio.get_running_loop()

        def _resolve_weights() -> Path:
            """Weights file from a file path or a directory (in that order)."""
            candidate = Path(model_path)
            if candidate.is_file():
                return candidate
            model_dir = candidate
            weights_file = model_dir / "model.pth"
            if not weights_file.exists():
                weights_file = model_dir / "osnet_ain_x1_0_msmt17.pth"
            if not weights_file.exists():
                # Try any .pth file in directory
                pth_files = sorted(model_dir.glob("*.pth"))
                if not pth_files:
                    msg = f"No model weights found in {model_dir}"
                    raise FileNotFoundError(msg)
                weights_file = pth_files[0]
            return weights_file

        def _load() -> dict[str, Any]:
            """Load model synchronously."""
            weights_file = _resolve_weights()

            # F12: verify the pin over the bytes BEFORE any deserialization.
            if expected_sha256:
                actual = _sha256(weights_file)
                if actual != expected_sha256:
                    msg = (
                        f"OSNet weights sha256 mismatch for {weights_file.name}: "
                        f"got {actual}, pinned {expected_sha256} — the file is not "
                        "the build models.yml pins (never loaded, never run)"
                    )
                    raise RuntimeError(msg)

            belt = _model_id(OSNET_ZOO_NAME, weights_file, expected_sha256)

            # Try to load torchreid OSNet if available
            try:
                # B2: torchreid's package chain imports
                # torch.utils.tensorboard (needs the tensorboard package,
                # unshipped); inert stub when the real one is absent.
                _ensure_tensorboard_importable()
                build_model = _import_build_model()

                # Build OSNet-AIN x1.0 architecture
                model = build_model(
                    name="osnet_ain_x1_0",
                    num_classes=1,  # We only need feature extraction
                    pretrained=False,
                )

                state_dict = torch.load(weights_file, map_location="cpu", weights_only=True)

                # Handle 'module.' prefix from DataParallel training (NEM-3888)
                if any(k.startswith("module.") for k in state_dict):
                    state_dict = {k.replace("module.", ""): v for k, v in state_dict.items()}
                    logger.debug("Stripped 'module.' prefix from state dict keys")

                # Filter out classifier keys to avoid shape mismatch (NEM-3888)
                # Pretrained weights may have classifier.weight shape [4101, 512] (MSMT17)
                # but model is instantiated with num_classes=1, giving [1, 512]
                classifier_keys = [k for k in state_dict if k.startswith("classifier")]
                if classifier_keys:
                    for key in classifier_keys:
                        del state_dict[key]
                    logger.debug(f"Filtered out classifier keys: {classifier_keys}")

                # NEM-4521: Load state dict and validate key matching
                load_result = model.load_state_dict(state_dict, strict=False)
                missing_keys = list(getattr(load_result, "missing_keys", []))
                unexpected_keys = list(getattr(load_result, "unexpected_keys", []))

                # Define critical keys that must be present (convolution and feature extraction layers)
                critical_prefixes = ["conv1.", "conv2.", "conv3.", "conv4.", "conv5.", "bn"]

                # Check if any critical keys are missing
                critical_missing = [
                    k for k in missing_keys if any(k.startswith(p) for p in critical_prefixes)
                ]
                if critical_missing:
                    error_msg = (
                        f"Critical OSNet weights missing: {critical_missing[:5]}... "
                        f"(total {len(critical_missing)} missing). "
                        "This will cause degraded Re-ID accuracy. "
                        "Check model architecture compatibility."
                    )
                    logger.error(error_msg)
                    raise RuntimeError(error_msg)

                # Log warnings for non-critical missing keys
                if missing_keys:
                    logger.warning(
                        f"OSNet state dict: {len(missing_keys)} missing keys "
                        f"(expected for classifier): {missing_keys[:3]}..."
                    )

                # Log info about unexpected keys (shouldn't happen but good to know)
                if unexpected_keys:
                    logger.warning(
                        f"OSNet state dict: {len(unexpected_keys)} unexpected keys: {unexpected_keys[:3]}..."
                    )

                logger.info(
                    f"Loaded OSNet-AIN x1.0 weights from {weights_file} "
                    f"(model_id={belt}, verified critical layers)"
                )

            except ImportError:
                # Fallback: load as generic feature extractor
                # This creates a simple wrapper that can load saved ONNX or TorchScript
                logger.info("torchreid not available, trying direct model load")

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
                "model_id": belt,
                "embedding_dim": OSNET_EMBEDDING_DIM,
            }

        result = await loop.run_in_executor(None, _load)

        logger.info(f"Successfully loaded OSNet-AIN x1.0 model from {model_path}")
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

        loop = asyncio.get_running_loop()

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

            embedding = _enforce_embedding_dim(embedding)

            # L2 normalize the embedding
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm

            return PersonEmbeddingResult(
                embedding=embedding,
                detection_id=detection_id,
                confidence=confidence,
                model_id=model_dict.get("model_id"),
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

        loop = asyncio.get_running_loop()

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
                # D-5: 512 dims or a loud refusal — never pad/truncate.
                processed = _enforce_embedding_dim(raw_embedding)

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
                        model_id=model_dict.get("model_id"),
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
