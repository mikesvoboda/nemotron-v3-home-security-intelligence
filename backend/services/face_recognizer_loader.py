"""CPU ONNX face-embedding loader — the face-recognizer model-zoo entry (rev 6, F11).

Owner ruling F11 (2026-09-26), condition 1: this is a model-zoo loader against a
FIXED INTERFACE — aligned face crop in, L2-normalized 512-d vector out — running
on **CPU onnxruntime**, with "weights absent means unavailable". No weights are
hard-wired here: the license review is open (the obvious zoo candidates carry
non-commercial-research-only terms), so the `face-recognizer` row in models.yml
is `enabled: false` with `license_status: pending-license` until the owner sends
the pick. Nothing in this module names a candidate.

Condition 2 (one embedding space end to end): `model_id` identifies the space —
it embeds the weights filename, so changing the weights file changes the id and
every stored `FaceEmbedding` carrying the old id stops matching (the matcher
surfaces "unavailable (re-enroll)" instead of a score). The dim guard below is
the same doctrine at the vector level: weights that do not emit exactly 512-d
do not speak the gallery's space and fail loud, never normalize and pass.

CPU-only by ruling (S4: out of the VRAM budget). The provider list is exactly
["CPUExecutionProvider"] — no GPU fallback, no CUDA ever.

House style follows fast_alpr_loader.py / osnet_loader.py: async
``load_*`` bound in ``model_zoo._LOADER_MAP``, optional dep behind an extras
(``uv sync --extra face``), blocking work off the event loop.

Usage:
    model = await load_face_recognizer(settings path)   # or raises Unavailable
    vec = extract_face_embedding(model["session"], aligned_crop)
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Any

from backend.core.logging import get_logger

if TYPE_CHECKING:
    from PIL import Image

logger = get_logger(__name__)

#: The gallery's space (F11 ruling 2). Stored FaceEmbedding vectors are 512-d
#: (ArcFace-shaped, face_identity.py); any weights emitting another dim are a
#: different space and are rejected here, at load/extract time, not in the
#: matcher's cosine.
FACE_EMBEDDING_DIM = 512

#: Standard ArcFace-style input crop the interface promises ("aligned face crop
#: in"). Crops that arrive at another size are resized, never re-aligned — face
#: alignment is the detector's business (face_detector.py), not the extractor's.
FACE_INPUT_SIZE = (112, 112)


class FaceRecognizerError(Exception):
    """The extractor is present but something about it is wrong (bad weights,
    wrong output space, inference failure)."""


class FaceRecognizerUnavailable(FaceRecognizerError):
    """The ruling's "unavailable": weights absent, weights unreadable, or
    onnxruntime not installed (the sandbox/CI truth — ``[face]`` extra).

    Callers render this as the face specialist's "unavailable" outcome; it must
    never block a VLM verdict (spec §6) and never impersonate "unknown"."""


def _find_weights(weights_dir: Path) -> Path:
    """Pick the single .onnx weights file in ``weights_dir``.

    Absence (no dir, no .onnx) is Unavailable per the ruling. More than one is
    an ambiguous pick — the model id embeds the filename, so WHICH file is
    loaded is a identity decision and not ours to guess.
    """
    if not weights_dir.is_dir():
        raise FaceRecognizerUnavailable(f"face-recognizer weights dir absent: {weights_dir}")
    candidates = sorted(weights_dir.glob("*.onnx"))
    if not candidates:
        raise FaceRecognizerUnavailable(
            f"no .onnx weights in {weights_dir} — face-recognizer is unavailable "
            "(weights pending the license pick; see models.yml face-recognizer row)"
        )
    if len(candidates) > 1:
        raise FaceRecognizerError(
            f"ambiguous face-recognizer weights in {weights_dir}: {', '.join(c.name for c in candidates)}"
        )
    return candidates[0]


async def load_face_recognizer(model_path: str) -> dict[str, Any]:
    """Load the CPU ONNX face recognizer from ``model_path`` (the model-zoo dir).

    Returns a dict::

        {"session": <onnxruntime.InferenceSession>, "input_name": str,
         "model_id": "face-recognizer@<weights-stem>", "embedding_dim": 512}

    Raises:
        FaceRecognizerUnavailable: weights absent (the ruling) or onnxruntime
            not installed — NEVER a bare ImportError escaping into a batch.
        FaceRecognizerError: ambiguous weights or session construction failure.
    """
    weights = _find_weights(Path(model_path))

    try:
        import onnxruntime as ort
    except ImportError as e:  # the sandbox/CI truth: no onnxruntime install
        raise FaceRecognizerUnavailable(
            "onnxruntime not installed — face recognition unavailable "
            "(install with: uv sync --extra face)"
        ) from e

    loop = asyncio.get_running_loop()

    def _build() -> Any:
        # CPU per the ruling, exactly: the provider list is the enforcement.
        return ort.InferenceSession(str(weights), providers=["CPUExecutionProvider"])

    try:
        session = await loop.run_in_executor(None, _build)
    except Exception as e:
        raise FaceRecognizerError(
            f"failed to load face-recognizer weights {weights.name}: {e}"
        ) from e

    inputs = session.get_inputs()
    model_id = f"face-recognizer@{weights.stem}"
    logger.info(f"face-recognizer loaded (model_id={model_id}, provider=CPU)")
    return {
        "session": session,
        "input_name": inputs[0].name if inputs else "input",
        "model_id": model_id,
        "embedding_dim": FACE_EMBEDDING_DIM,
    }


def preprocess_face_crop(crop: Image.Image) -> Any:
    """Aligned crop -> float32 CHW (1, 3, 112, 112) in [-1, 1].

    The standard ArcFace-family preprocessing: RGB, resized to 112x112, scaled
    to [-1, 1]. The weights pick may want its own mean/std; that normalization
    lives HERE (the interface's preprocessing), keyed off the model id, when a
    per-weights table is needed — not in each caller.
    """
    import numpy as np
    from PIL import Image as PILImage

    resized = crop.convert("RGB").resize(FACE_INPUT_SIZE, PILImage.BILINEAR)
    arr = np.asarray(resized, dtype=np.float32) / 127.5 - 1.0  # [0,255] -> [-1,1]
    arr = arr.transpose(2, 0, 1)[None]  # HWC -> CHW with batch dim
    return np.ascontiguousarray(arr, dtype=np.float32)


def extract_face_embedding(session: Any, crop: Image.Image) -> list[float]:
    """Embed one aligned face crop: **the** L2-normalized 512-d vector.

    Synchronous pure function (session.run is CPU-bound; async callers wrap it
    in run_in_executor like every other specialist here). The loader does the
    L2 step itself — real sessions do NOT normalize — and guards the output
    dimension before normalizing, so a wrong-space model fails loud.
    """
    import numpy as np

    feed = preprocess_face_crop(crop)
    try:
        raw = session.run(None, {"input": feed})
    except Exception as e:
        raise FaceRecognizerError(f"face-recognizer inference failed: {e}") from e

    vector = np.asarray(raw[0], dtype=np.float32).reshape(-1)
    if vector.shape[0] != FACE_EMBEDDING_DIM:
        raise FaceRecognizerError(
            f"face-recognizer emitted {vector.shape[0]}-d, gallery space is "
            f"{FACE_EMBEDDING_DIM}-d — wrong weights for this gallery "
            f"(expected a 512-d embedding space)"
        )
    norm = float(np.linalg.norm(vector))
    if not norm > 0.0:
        raise FaceRecognizerError("face-recognizer emitted the zero vector")
    return [float(v) for v in (vector / norm)]
