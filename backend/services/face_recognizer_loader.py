"""Face-leg loaders — SCRFD + w600k_r50 on CPU onnxruntime (rev 6/7, F11 + F12).

The face leg loads EXACTLY TWO ONNX files from the InsightFace buffalo_l
pack — never the insightface package's FaceAnalysis, which drags in all five
pack models (that loader, on GPU, is where the old "~1.5 GB VRAM" figure came
from):

- ``scrfd_10g_bnkps.onnx`` (SCRFD-10G-KPS): face boxes + 5 landmarks; the
  landmarks drive the ArcFace 5-point alignment (F12: yolo11-face gives boxes
  only, so its crops can't be aligned and quietly lose embedder accuracy).
- ``w600k_r50.onnx``: the embedder behind the F11 interface — aligned
  112x112 crop in, L2-normalized 512-d vector out.

Both files are pinned by SHA-256 in their models.yml rows and the pin is
enforced HERE: wrong bytes are reported exactly like missing bytes —
``FaceRecognizerUnavailable`` (F12: absent weights mean unavailable; a mirror
shipping a different build must not silently fork the gallery's embedding
space). CPU-only by ruling (S4: out of the VRAM budget) — the provider list
``["CPUExecutionProvider"]`` is the enforcement, no CUDA ever.

F11 ruling 2 (one embedding space end to end): ``model_id`` embeds the
weights filename AND content hash, so changing the bytes changes the id and
every stored ``FaceEmbedding`` carrying the old id stops matching — the
matcher surfaces "unavailable (re-enroll)" instead of a score. The dim guard
in ``extract_face_embedding`` is the same doctrine at the vector level.

House style follows fast_alpr_loader.py / osnet_loader.py: async ``load_*``
bound in ``model_zoo._LOADER_MAP``, the optional dep behind an extras
(``uv sync --extra face``), blocking work off the event loop. The decode math
is a numpy port of insightface's scrfd.py (blob (x-127.5)/128 RGB, strides
8/16/32, distance decode, greedy NMS 0.4) — the reference kept for the shapes
only; the package itself is never a dependency.

Usage:
    det = await load_face_detector(settings path)      # or raises Unavailable
    faces = detect_faces(det["session"], image)        # boxes + landmarks
    rec = await load_face_recognizer(settings path)    # or raises Unavailable
    crop = align_face_crop(image, faces[0].landmarks)
    vec = extract_face_embedding(rec["session"], crop)
"""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
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

#: w600k_r50's input size. The interface promises an ALIGNED crop at this
#: size; resizing a crop that arrives elsewhere is still the caller's job to
#: have ALIGNED (align_face_crop), not the extractor's to fix.
FACE_INPUT_SIZE = (112, 112)

#: The ArcFace 5-point reference template (left eye, right eye, nose, left
#: mouth, right mouth) in the 112x112 crop — the insightface/InsightFace
#: standard landmark template used to train w600k_r50's crop distribution.
ARCFACE_TEMPLATE = [
    (38.2946, 51.6963),
    (73.5318, 51.5014),
    (56.0252, 68.4922),
    (41.5493, 92.2507),
    (70.7299, 92.4101),
]

#: SCRFD-10g fixed anchor geometry (scrfd_10g_bnkps: 3 feature levels, 2
#: anchors per cell, strides 8/16/32 — insightface scrfd.py).
_SCRFD_FMC = 3
_SCRFD_STRIDES = (8, 16, 32)
_SCRFD_ANCHORS_PER_CELL = 2


class FaceRecognizerError(Exception):
    """The leg is present but something about it is wrong (unreadable ONNX,
    wrong output space, inference failure)."""


class FaceRecognizerUnavailable(FaceRecognizerError):
    """The ruling's "unavailable": weights absent, weights that fail the
    sha256 pin, or onnxruntime not installed (the sandbox/CI truth — the
    ``[face]`` extra).

    Callers render this as the face specialist's "unavailable" outcome; it
    must never block a VLM verdict (spec §6) and never impersonate "unknown"."""


@dataclass(frozen=True, slots=True)
class ScrfdFace:
    """One SCRFD detection in ORIGINAL image coordinates."""

    bbox: tuple[float, float, float, float]  # x1, y1, x2, y2
    score: float
    landmarks: Any = None  # (5, 2) float32 ndarray, or None


# ---------------------------------------------------------------------------
# Loading (shared): path -> hash-pinned CPU session
# ---------------------------------------------------------------------------


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


async def _load_cpu_session(weights: Path, expected_sha256: str | None) -> Any:
    """Hash-check (when pinned), then build a CPU-only InferenceSession off
    the loop. Absence / hash miss / ImportError all mean UNAVAILABLE (F12)."""
    if not weights.is_file():
        raise FaceRecognizerUnavailable(f"face weights absent: {weights}")
    if expected_sha256:
        actual = await asyncio.get_running_loop().run_in_executor(None, _sha256, weights)
        if actual != expected_sha256:
            raise FaceRecognizerUnavailable(
                f"face weights sha256 mismatch for {weights.name}: "
                f"got {actual}, pinned {expected_sha256} — the file is not the "
                "buffalo_l build models.yml pins (treated as unavailable, never run)"
            )

    try:
        import onnxruntime as ort
    except ImportError as e:  # the sandbox/CI truth: no onnxruntime install
        raise FaceRecognizerUnavailable(
            "onnxruntime not installed — face leg unavailable (install with: uv sync --extra face)"
        ) from e

    loop = asyncio.get_running_loop()

    def _build() -> Any:
        # CPU per the ruling, exactly: the provider list is the enforcement.
        return ort.InferenceSession(str(weights), providers=["CPUExecutionProvider"])

    try:
        return await loop.run_in_executor(None, _build)
    except Exception as e:
        raise FaceRecognizerError(f"failed to load face weights {weights.name}: {e}") from e


def _model_id(role: str, weights: Path, expected_sha256: str | None) -> str:
    """model_id identifies the embedding space (F11 ruling 2): filename plus
    the pinned hash prefix, so changing the weights bytes always changes the
    id the gallery stores and the matcher compares."""
    base = f"{role}@{weights.stem}"
    return f"{base}@{expected_sha256[:12]}" if expected_sha256 else base


async def load_face_recognizer(
    model_path: str, expected_sha256: str | None = None
) -> dict[str, Any]:
    """Load the w600k_r50 embedder (models.yml face-recognizer row passes
    ``expected_sha256`` from the row).

    Returns ``{"session", "input_name", "model_id", "embedding_dim": 512}``.
    Raises FaceRecognizerUnavailable (absent / hash miss / no onnxruntime) or
    FaceRecognizerError (unreadable ONNX) — never a bare ImportError.
    """
    weights = Path(model_path)
    session = await _load_cpu_session(weights, expected_sha256)
    inputs = session.get_inputs()
    logger.info(
        f"face-recognizer loaded (model_id={_model_id('face-recognizer', weights, expected_sha256)}, provider=CPU)"
    )
    return {
        "session": session,
        "input_name": inputs[0].name if inputs else "input.1",
        "model_id": _model_id("face-recognizer", weights, expected_sha256),
        "embedding_dim": FACE_EMBEDDING_DIM,
    }


async def load_face_detector(model_path: str, expected_sha256: str | None = None) -> dict[str, Any]:
    """Load SCRFD-10G-KPS (models.yml face-detector-scrfd row). Same
    degradation contract and shape as load_face_recognizer."""
    weights = Path(model_path)
    session = await _load_cpu_session(weights, expected_sha256)
    inputs = session.get_inputs()
    return {
        "session": session,
        "input_name": inputs[0].name if inputs else "input.1",
        "model_id": _model_id("face-detector-scrfd", weights, expected_sha256),
    }


# ---------------------------------------------------------------------------
# Embedding (F11 interface): aligned crop in, unit 512-d out
# ---------------------------------------------------------------------------


def preprocess_face_crop(crop: Image.Image) -> Any:
    """Aligned crop -> float32 CHW (1, 3, 112, 112) in [-1, 1].

    w600k_r50's standard preprocessing (ArcFace family): RGB, 112x112,
    (x-127.5)/127.5. The crop must ALREADY be aligned (align_face_crop);
    this only resizes, never re-aligns.
    """
    import numpy as np
    from PIL import Image as PILImage

    resized = crop.convert("RGB").resize(FACE_INPUT_SIZE, PILImage.BILINEAR)
    arr = np.asarray(resized, dtype=np.float32) / 127.5 - 1.0  # [0,255] -> [-1,1]
    arr = arr.transpose(2, 0, 1)[None]  # HWC -> CHW with batch dim
    return np.ascontiguousarray(arr, dtype=np.float32)


def extract_face_embedding(session: Any, crop: Image.Image) -> list[float]:
    """Embed one aligned face crop: **the** L2-normalized 512-d vector.

    Synchronous pure function (session.run is CPU-bound; async callers wrap
    it in run_in_executor like every other specialist here). The loader does
    the L2 step itself — real sessions do NOT normalize — and guards the
    output dimension before normalizing, so a wrong-space model fails loud.
    """
    import numpy as np

    feed = preprocess_face_crop(crop)
    try:
        raw = session.run(None, {"input.1": feed})
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


# ---------------------------------------------------------------------------
# Detection: numpy port of insightface's scrfd.py decode + greedy NMS
# ---------------------------------------------------------------------------


def _scrfd_blob(image: Any, input_size: tuple[int, int]) -> tuple[Any, float]:
    """Letterbox + normalize exactly like the model was trained:
    keep aspect, zero-pad bottom/right, RGB, (x-127.5)/128. Returns the blob
    and the resize scale (for mapping detections back)."""
    import numpy as np
    from PIL import Image as PILImage

    if isinstance(image, PILImage.Image):
        image = np.asarray(image.convert("RGB"))
    arr = np.asarray(image)
    ih, iw = arr.shape[0], arr.shape[1]
    tw, th = input_size
    ratio = min(tw / iw, th / ih)
    nw, nh = max(1, int(iw * ratio)), max(1, int(ih * ratio))
    resized = np.asarray(
        PILImage.fromarray(arr).resize((nw, nh), PILImage.BILINEAR), dtype=np.float32
    )
    canvas = np.zeros((th, tw, 3), dtype=np.float32)
    canvas[:nh, :nw, :] = resized
    blob = (canvas - 127.5) / 128.0  # insightface SCRFD: mean 127.5, std 128.0
    blob = np.ascontiguousarray(blob.transpose(2, 0, 1)[None], dtype=np.float32)
    return blob, ratio


def _nms(boxes: Any, scores: Any, iou_threshold: float = 0.4) -> list[int]:
    """Greedy score-ordered NMS (insightface's SCRFD.nms defaults: 0.4)."""
    import numpy as np

    order = np.argsort(-scores, kind="stable")
    keep: list[int] = []
    for idx in order:
        x1, y1, x2, y2 = boxes[idx]
        ok = True
        for k in keep:
            kx1, ky1, kx2, ky2 = boxes[k]
            ix1, iy1 = max(x1, kx1), max(y1, ky1)
            ix2, iy2 = min(x2, kx2), min(y2, ky2)
            iw_ih = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
            union = (x2 - x1) * (y2 - y1) + (kx2 - kx1) * (ky2 - ky1) - iw_ih
            if union > 0 and iw_ih / union > iou_threshold:
                ok = False
                break
        if ok:
            keep.append(int(idx))
    return keep


def detect_faces(
    session: Any,
    image: Any,
    input_size: tuple[int, int] = (640, 640),
    threshold: float = 0.6,
    nms_iou: float = 0.4,
) -> list[ScrfdFace]:
    """Run SCRFD: boxes + 5 landmarks in original-image coordinates.

    Decode is the insightface reference math (numpy port): per stride,
    anchor-cell centers x stride, distance-decoded boxes (l,t,r,b) and 5x2
    landmark offsets, scores >= threshold; then score-ordered greedy NMS and
    the letterbox inverse. Outputs are read in the real buffalo layout:
    net_outs = [scores x3, dboxes x3, dkps x3], flat (anchors, C) rows in
    cell-major order, 2 anchors per cell."""
    import numpy as np

    blob, scale = _scrfd_blob(image, input_size)
    try:
        net_outs = session.run(None, {"input.1": blob})
    except Exception as e:
        raise FaceRecognizerError(f"face-detector inference failed: {e}") from e

    h_in, w_in = blob.shape[2], blob.shape[3]
    all_scores: list[Any] = []
    all_boxes: list[Any] = []
    all_kps: list[Any] = []
    for idx, stride in enumerate(_SCRFD_STRIDES):
        scores = np.asarray(net_outs[idx], dtype=np.float32).reshape(-1)
        dbox = np.asarray(net_outs[idx + _SCRFD_FMC], dtype=np.float32).reshape(-1, 4) * stride
        dkps = np.asarray(net_outs[idx + 2 * _SCRFD_FMC], dtype=np.float32).reshape(-1, 10) * stride
        h, w = h_in // stride, w_in // stride
        # Anchor grid exactly as insightface builds it: cell centers in
        # (row, col) order, each cell repeated for its anchors -> flat row
        # index (row * W + col) * anchors_per_cell + anchor.
        centers = (np.stack(np.mgrid[:h, :w][::-1], axis=-1).astype(np.float32) * stride).reshape(
            -1, 2
        )
        if _SCRFD_ANCHORS_PER_CELL > 1:
            centers = np.stack([centers] * _SCRFD_ANCHORS_PER_CELL, axis=1).reshape(-1, 2)
        centers = centers[: scores.shape[0]]
        pos = np.where(scores >= threshold)[0]
        if pos.size == 0:
            continue
        c = centers[pos]
        boxes = np.stack(
            [
                c[:, 0] - dbox[pos, 0],
                c[:, 1] - dbox[pos, 1],
                c[:, 0] + dbox[pos, 2],
                c[:, 1] + dbox[pos, 3],
            ],
            axis=1,
        )
        kps = (c[:, None, :] + dkps[pos].reshape(-1, 5, 2)).reshape(-1, 10)
        all_scores.append(scores[pos])
        all_boxes.append(boxes)
        all_kps.append(kps)

    if not all_scores:
        return []

    scores = np.concatenate(all_scores)
    boxes = np.concatenate(all_boxes) / scale  # letterbox inverse (pad is bottom-right)
    kps = np.concatenate(all_kps) / scale

    faces: list[ScrfdFace] = []
    for i in _nms(boxes, scores, nms_iou):
        x1, y1, x2, y2 = boxes[i]
        landmarks = kps[i].reshape(5, 2) if kps.shape[1] == 10 else None
        faces.append(
            ScrfdFace(
                bbox=(float(x1), float(y1), float(x2), float(y2)),
                score=float(scores[i]),
                landmarks=landmarks,
            )
        )
    return faces


# ---------------------------------------------------------------------------
# Alignment: ArcFace 5-point similarity transform (numpy least squares)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Similarity:
    """src -> dst affine [a -b tx; b a ty] (scale a+bi, rotation, translate)."""

    a: float
    b: float
    tx: float
    ty: float

    def apply(self, pt: Any) -> Any:
        x, y = float(pt[0]), float(pt[1])
        return (self.a * x - self.b * y + self.tx, self.b * x + self.a * y + self.ty)


def alignment_transform(landmarks: Any) -> _Similarity:
    """Least-squares similarity transform from the 5 detected landmarks onto
    ARCFACE_TEMPLATE (the insightface warp: scale+rotation+translation, the
    crop's whole job)."""
    import numpy as np

    src = np.asarray(landmarks, dtype=np.float64).reshape(-1, 2)
    dst = np.asarray(ARCFACE_TEMPLATE, dtype=np.float64).reshape(-1, 2)
    n = src.shape[0]
    design = np.zeros((2 * n, 4))
    design[0::2] = np.column_stack([src[:, 0], -src[:, 1], np.ones(n), np.zeros(n)])
    design[1::2] = np.column_stack([src[:, 1], src[:, 0], np.zeros(n), np.ones(n)])
    target = dst.reshape(-1)
    (a, b, tx, ty), *_ = np.linalg.lstsq(design, target, rcond=None)
    return _Similarity(a=a, b=b, tx=tx, ty=ty)


def align_face_crop(image: Any, landmarks: Any) -> Image.Image:
    """Warp the 112x112 aligned crop out of ``image`` at the 5 landmarks
    (inverse similarity transform sampled with PIL's affine; the reference
    uses cv2.warpAffine INTER_LINEAR — PIL BILINEAR is the same filter, and
    numpy-only keeps the dependency surface at the [face] extra)."""
    import numpy as np
    from PIL import Image as PILImage

    if isinstance(image, PILImage.Image):
        image = np.asarray(image.convert("RGB"))
    src = np.asarray(landmarks, dtype=np.float64).reshape(-1, 2)
    tmpl = np.asarray(ARCFACE_TEMPLATE, dtype=np.float64)
    # dst -> src is the inverse of the src->dst similarity solve: fit it by
    # swapping the roles (least squares on the reverse pair set).
    inv = alignment_transform_from_to(tmpl, src)
    coeffs = (inv.a, -inv.b, inv.tx, inv.b, inv.a, inv.ty)
    pil = PILImage.fromarray(np.ascontiguousarray(np.asarray(image, dtype=np.uint8)))
    return pil.transform(FACE_INPUT_SIZE, PILImage.AFFINE, coeffs, resample=PILImage.BILINEAR)


def alignment_transform_from_to(src: Any, dst: Any) -> _Similarity:
    """General least-squares similarity fit src -> dst (the template constant
    is the specialization ``alignment_transform`` publishes)."""
    import numpy as np

    src = np.asarray(src, dtype=np.float64).reshape(-1, 2)
    dst = np.asarray(dst, dtype=np.float64).reshape(-1, 2)
    n = src.shape[0]
    design = np.zeros((2 * n, 4))
    design[0::2] = np.column_stack([src[:, 0], -src[:, 1], np.ones(n), np.zeros(n)])
    design[1::2] = np.column_stack([src[:, 1], src[:, 0], np.zeros(n), np.ones(n)])
    target = dst.reshape(-1)
    (a, b, tx, ty), *_ = np.linalg.lstsq(design, target, rcond=None)
    return _Similarity(a=a, b=b, tx=tx, ty=ty)
