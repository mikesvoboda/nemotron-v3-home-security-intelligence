"""Person re-ID through the AI gateway's ``/enrich-lt/person-reid`` (B2.2).

Owner ruling 68 moves the backend's person re-ID from its CPU OSNet copy to the
gateway's ``reid`` model on the GPU: the same network and weights. This module
is the gateway half of the seam behind ``osnet_loader.extract_person_embedding``.

- The crop travels as PNG, so the wire is lossless: the gateway decodes the same
  pixels the local path would have used.
- The returned vector is L2-normalised here, whatever the gateway did, so both
  paths hand callers the same final vector.
- The model ID is the one the gateway reports. When it reports none, the vector
  carries ``LEGACY_MODEL_ID``, which ``compare_person_vectors`` refuses; it is
  never relabelled with an enrolled row's ID.
- Any transport or server failure raises ``ReidGatewayUnavailable`` (a
  ``RuntimeError``, the seam's failure contract), so the leg can degrade with
  its own reason code.
"""

from __future__ import annotations

import base64
import io
from typing import TYPE_CHECKING, Any

import httpx
import numpy as np

from backend.core.vector_provenance import LEGACY_MODEL_ID

if TYPE_CHECKING:
    from PIL import Image

    from backend.services.osnet_loader import PersonEmbeddingResult

#: The gateway's OSNet output dimension; anything else is not this model.
EMBEDDING_DIM = 512

#: Per-request timeout. One crop is one request; the GPU path answers in
#: milliseconds, so this bounds a hung gateway, not normal latency. The leg
#: stops at the first outage, so a hung gateway costs one timeout per event.
DEFAULT_TIMEOUT_SECONDS = 3.0


class ReidGatewayUnavailable(RuntimeError):
    """The gateway could not produce an embedding (down, erroring, unreachable)."""


def crop_confidence(width: int, height: int) -> float:
    """The local path's crop-quality confidence, so both paths agree."""
    if width < 32 or height < 64:
        return 0.5
    if width < 64 or height < 128:
        return 0.8
    return 1.0


def encode_crop_png(image: Image.Image) -> str:
    """Base64 PNG of the crop in RGB: lossless, so the gateway sees these pixels."""
    rgb = image.convert("RGB") if image.mode != "RGB" else image
    buf = io.BytesIO()
    rgb.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


async def embed_person_via_gateway(
    image: Image.Image,
    *,
    base_url: str,
    detection_id: str | None = None,
    client: httpx.AsyncClient | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> PersonEmbeddingResult:
    """One person crop -> its final OSNet vector, via ``{base_url}/person-reid``.

    Raises:
        ReidGatewayUnavailable: the request failed or the gateway answered an error.
        RuntimeError: the gateway answered with something that is not a 512-d vector.
    """
    from backend.services.osnet_loader import PersonEmbeddingResult

    url = f"{base_url.rstrip('/')}/person-reid"
    payload = {"image": encode_crop_png(image)}
    try:
        if client is None:
            async with httpx.AsyncClient(timeout=timeout) as owned:
                response = await owned.post(url, json=payload)
        else:
            response = await client.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
        body: dict[str, Any] = response.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code < 500:
            # The gateway is up and refused this crop (400: undecodable image).
            raise RuntimeError(f"person re-ID gateway rejected the crop: {e}") from e
        raise ReidGatewayUnavailable(f"person re-ID gateway call failed: {e}") from e
    except (httpx.HTTPError, ValueError) as e:
        raise ReidGatewayUnavailable(f"person re-ID gateway call failed: {e}") from e

    vector = np.asarray(body.get("embedding") or [], dtype=np.float32)
    if vector.shape != (EMBEDDING_DIM,):
        raise RuntimeError(
            f"person re-ID gateway returned shape {vector.shape}, expected ({EMBEDDING_DIM},)"
        )
    norm = float(np.linalg.norm(vector))
    if norm > 0:
        vector = vector / norm

    width, height = image.size
    return PersonEmbeddingResult(
        embedding=vector,
        detection_id=detection_id,
        confidence=crop_confidence(width, height),
        model_id=body.get("model_id") or LEGACY_MODEL_ID,
    )
