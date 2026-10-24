"""OSNet person re-identification gateway seam ([r306b]).

Ruling 306 (`[r306a]`, `[r306b]`; UR-85) moved person re-identification onto the
AI gateway's GPU `reid` model (`/enrich-lt/person-reid`) and removed the
backend's resident CPU OSNet copy.

Model details:
- Architecture: OSNet-AIN x1.0 (served by Triton `reid` behind `/enrich-lt/person-reid`)
- Input: 256x128 person crops
- Output: 512-dimensional L2-normalized embedding vectors
- Provenance: `osnet-ain-x1-0@osnet_ain_x1_0_msmt17@8a07e8da3894` (`models.yml`)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from backend.core.config import get_settings
from backend.core.logging import get_logger

if TYPE_CHECKING:
    from PIL import Image

logger = get_logger(__name__)

# OSNet-AIN x1.0 embedding dimension
OSNET_EMBEDDING_DIM = 512

# The zoo name of the row that owns these weights (models.yml is the single
# source: weights file + sha256 pin + belt, all read from it).
OSNET_ZOO_NAME = "osnet-ain-x1-0"

# OSNet input geometry and ImageNet normalisation. The gateway's
# /enrich-lt/person-reid preprocesses with the same values (B2.2 parity gate).
OSNET_INPUT_HEIGHT = 256
OSNET_INPUT_WIDTH = 128
OSNET_MEAN = (0.485, 0.456, 0.406)
OSNET_STD = (0.229, 0.224, 0.225)


def _osnet_zoo_row() -> dict[str, Any]:
    """The osnet row of models.yml, read directly (NOT via model_zoo: the
    zoo imports THIS module, so a module-level import would be a cycle)."""
    import yaml

    models_yml = Path(__file__).resolve().parents[2] / "models.yml"
    entries: list[dict[str, Any]] = yaml.safe_load(models_yml.read_text())["models"]
    for entry in entries:
        if entry.get("name") == OSNET_ZOO_NAME:
            return entry
    return {}


def osnet_model_id() -> str:
    """THE belt string for every OSNet person vector (F11, ledger item 20).

    Grammar is ``role@weightsfile@sha[:12]`` and the value is DERIVED from the
    models.yml row — never a literal — so the backend handle, the Triton ``reid``
    producer's payload labels, and the safe-extract payloads all stamp ONE string.
    """
    row = _osnet_zoo_row()
    weights_file = str(row.get("runtime_file") or "osnet_ain_x1_0_msmt17.pth")
    stem = Path(weights_file).stem
    sha = str(row.get("sha256") or "")
    return f"{OSNET_ZOO_NAME}@{stem}@{sha[:12]}" if sha else f"{OSNET_ZOO_NAME}@{stem}"


def _model_id(role: str, weights: Path, expected_sha256: str | None) -> str:
    """Load-time belt: the id names the weights file plus the satisfied pin."""
    base = f"{role}@{weights.stem}"
    return f"{base}@{expected_sha256[:12]}" if expected_sha256 else base


def _enforce_embedding_dim(embedding: np.ndarray) -> np.ndarray:
    """D-5: a 512-d vector or a loud refusal — never a coerced one."""
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
    """Return the gateway handle for person re-ID ([r306b]).

    Its ``model_id`` is None: the belt is the ID the gateway reports on each
    embedding, never assumed.
    """
    settings = get_settings()
    return {"kind": "gateway", "base_url": settings.enrichment_light_url, "model_id": None}


@dataclass(slots=True)
class PersonEmbeddingResult:
    """Result from OSNet person re-identification embedding extraction."""

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
        """Calculate cosine similarity with another embedding."""
        norm_self = self.embedding / (np.linalg.norm(self.embedding) + 1e-8)
        norm_other = other.embedding / (np.linalg.norm(other.embedding) + 1e-8)
        return float(np.dot(norm_self, norm_other))


async def load_osnet_model(model_path: str, expected_sha256: str | None = None) -> dict[str, Any]:
    """Build the gateway handle for OSNet-AIN x1.0 ([r306b])."""
    from backend.core.security import PathSecurityError, validate_model_path

    try:
        validate_model_path(
            model_path,
            allowed_extensions=frozenset(),
            must_exist=False,
        )
    except PathSecurityError as e:
        raise RuntimeError(f"Invalid model path: {e}") from e

    candidate = Path(model_path)
    weights_file = candidate if candidate.suffix == ".pth" else Path("osnet_ain_x1_0_msmt17.pth")
    belt = (
        _model_id(OSNET_ZOO_NAME, weights_file, expected_sha256)
        if expected_sha256
        else osnet_model_id()
    )
    settings = get_settings()
    return {
        "kind": "gateway",
        "base_url": settings.enrichment_light_url,
        "model_id": belt,
        "embedding_dim": OSNET_EMBEDDING_DIM,
    }


async def extract_person_embedding(
    model_dict: dict[str, Any],
    image: Image.Image,
    detection_id: str | None = None,
) -> PersonEmbeddingResult:
    """Extract person re-identification embedding via the AI gateway ([r306b])."""
    from backend.services import reid_gateway

    base_url = model_dict.get("base_url") or get_settings().enrichment_light_url
    return await reid_gateway.embed_person_via_gateway(
        image, base_url=str(base_url), detection_id=detection_id
    )


async def extract_person_embeddings_batch(
    model_dict: dict[str, Any],
    images: list[Image.Image],
    detection_ids: list[str] | None = None,
) -> list[PersonEmbeddingResult]:
    """Batch person embedding is not supported on the gateway path; embed per crop."""
    del model_dict, images, detection_ids
    raise RuntimeError("batch person embedding is local-only; a gateway handle embeds per crop")


def match_person_embeddings(
    query: PersonEmbeddingResult,
    gallery: list[PersonEmbeddingResult],
    threshold: float = 0.7,
) -> list[tuple[PersonEmbeddingResult, float]]:
    """Find matching persons in a gallery based on embedding similarity."""
    matches = []
    for gallery_embedding in gallery:
        similarity = query.cosine_similarity(gallery_embedding)
        if similarity >= threshold:
            matches.append((gallery_embedding, similarity))
    matches.sort(key=lambda x: x[1], reverse=True)
    return matches


def format_person_reid_context(
    matches: list[tuple[PersonEmbeddingResult, float]],
    detection_id: str,
) -> str:
    """Format person re-identification matches for prompt context."""
    if not matches:
        return f"Person {detection_id}: No prior matches found (new individual)"

    lines = [f"Person {detection_id} re-identification:"]
    for match, similarity in matches[:3]:
        match_id = match.detection_id or "unknown"
        sim_pct = f"{similarity:.0%}"
        if similarity >= 0.9:
            lines.append(f"  - HIGH CONFIDENCE match to {match_id} ({sim_pct})")
        elif similarity >= 0.8:
            lines.append(f"  - Likely same person as {match_id} ({sim_pct})")
        else:
            lines.append(f"  - Possible match to {match_id} ({sim_pct})")

    return "\n".join(lines)
