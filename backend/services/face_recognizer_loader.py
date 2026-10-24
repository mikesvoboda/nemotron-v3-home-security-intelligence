"""Face-leg gateway client + geometry — SCRFD + w600k_r50 via Triton ([r307b], F11 + F12).

Ruling 307 (`[r307a]`, `[r307b]`; UR-86) moves the face leg onto the GPU
through the AI gateway's `/enrich-lt/face-detect` (Triton `scrfd` TensorRT plan)
and `/enrich-lt/face-recognize` (Triton `arcface` TensorRT plan) routes while
keeping every F11/F12 invariant except "CPU":

- Exactly two SHA-256-pinned ONNX files in `models.yml` (`scrfd_10g_bnkps.onnx`
  and `w600k_r50.onnx`), never `insightface.FaceAnalysis`.
- Stored face embeddings keep their model IDs (`face-detector-scrfd@scrfd_10g_bnkps@5838f7fe0536`
  and `face-recognizer@w600k_r50@4c06341c33c2`).
- The gateway response's `model_id` is verified against the `models.yml` SHA-256
  pin before any detection or vector is accepted: a gateway without the pinned
  weights (or the fake-AI stack's unpinned sentinel) raises
  `FaceRecognizerUnavailable`, so the specialist stage degrades to
  `unavailable` and enrollment refuses rather than storing unverified vectors.
"""

from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

# The provenance vocabulary is a dependency-free leaf in backend/core (the
# ORM needs the same constant and may not import a service; see
# backend/core/face_provenance.py). Re-exported here because the leg is
# where honest ids are minted.
from backend.core.face_provenance import LEGACY_MODEL_ID  # noqa: F401 (re-export)
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

#: Per-request gateway timeout (matches reid_gateway.py).
DEFAULT_TIMEOUT_SECONDS = 3.0

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

_DETRACTOR_NAME = "face-detector-scrfd"
_RECOGNIZER_NAME = "face-recognizer"


class FaceRecognizerError(Exception):
    """The leg is present but something about it is wrong (unreadable image,
    wrong output space, inference failure)."""


class FaceRecognizerUnavailable(FaceRecognizerError):
    """The ruling's "unavailable": weights absent, weights that fail the
    sha256 pin, or gateway unreachable.

    Callers render this as the face specialist's "unavailable" outcome; it
    must never block a VLM verdict (spec §6) and never impersonate "unknown"."""


@dataclass(frozen=True, slots=True)
class ScrfdFace:
    """One SCRFD detection in ORIGINAL image coordinates."""

    bbox: tuple[float, float, float, float]  # x1, y1, x2, y2
    score: float
    landmarks: Any = None  # (5, 2) float32 ndarray, or None


# ---------------------------------------------------------------------------
# Provenance & gateway handles ([r307b], F11 + F12)
# ---------------------------------------------------------------------------


def _model_id(role: str, weights: Path, expected_sha256: str | None) -> str:
    """model_id identifies the embedding space (F11 ruling 2): filename plus
    the pinned hash prefix, so changing the weights bytes always changes the
    id the gallery stores and the matcher compares."""
    base = f"{role}@{weights.stem}"
    return f"{base}@{expected_sha256[:12]}" if expected_sha256 else base


def _zoo_row(name: str) -> dict[str, Any]:
    """Read a row directly from models.yml (avoids importing model_zoo at module level)."""
    import yaml

    models_yml = Path(__file__).resolve().parents[2] / "models.yml"
    entries: list[dict[str, Any]] = yaml.safe_load(models_yml.read_text())["models"]
    for entry in entries:
        if entry.get("name") == name:
            return entry
    return {}


def face_detector_model_id() -> str:
    """The pinned SCRFD model ID derived from `models.yml` (`face-detector-scrfd@scrfd_10g_bnkps@5838f7fe0536`)."""
    row = _zoo_row(_DETRACTOR_NAME)
    weights_file = str(row.get("runtime_file") or "scrfd_10g_bnkps.onnx")
    sha = str(row.get("sha256") or "")
    return _model_id(_DETRACTOR_NAME, Path(weights_file), sha or None)


def face_recognizer_model_id() -> str:
    """The pinned ArcFace model ID derived from `models.yml` (`face-recognizer@w600k_r50@4c06341c33c2`)."""
    row = _zoo_row(_RECOGNIZER_NAME)
    weights_file = str(row.get("runtime_file") or "w600k_r50.onnx")
    sha = str(row.get("sha256") or "")
    return _model_id(_RECOGNIZER_NAME, Path(weights_file), sha or None)


def _gateway_session(base_url: str, model_id: str) -> dict[str, Any]:
    return {"kind": "gateway", "base_url": base_url, "model_id": model_id}


def _encode_image_png_b64(image: Any) -> str:
    """Lossless RGB PNG base64 so the gateway receives the exact pixels."""
    import numpy as np
    from PIL import Image as PILImage

    if isinstance(image, PILImage.Image):
        rgb = image.convert("RGB") if image.mode != "RGB" else image
    else:
        rgb = PILImage.fromarray(np.ascontiguousarray(np.asarray(image, dtype=np.uint8))).convert(
            "RGB"
        )
    buf = io.BytesIO()
    rgb.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _post_gateway(
    session: dict[str, Any],
    route: str,
    payload: dict[str, Any],
    *,
    role: str,
    expected_model_id: str,
) -> dict[str, Any]:
    """POST to `{base_url}/{route}` and enforce the F12 SHA-256 `model_id` pin."""
    import httpx

    base_url = str(session.get("base_url") or "").rstrip("/")
    url = f"{base_url}/{route.lstrip('/')}"
    timeout = float(session.get("timeout") or DEFAULT_TIMEOUT_SECONDS)
    client: httpx.Client | None = session.get("client")
    try:
        if client is None:
            with httpx.Client(timeout=timeout) as owned:
                response = owned.post(url, json=payload)
        else:
            response = client.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
        body: dict[str, Any] = response.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code < 500:
            raise FaceRecognizerError(f"{role} gateway rejected request: {e}") from e
        raise FaceRecognizerUnavailable(
            f"face extractor unavailable: the pinned face weights are not loaded ({role} gateway HTTP {e.response.status_code})"
        ) from e
    except (httpx.HTTPError, ValueError) as e:
        raise FaceRecognizerUnavailable(
            f"face extractor unavailable: the pinned face weights are not loaded ({role} gateway unavailable: {e})"
        ) from e

    reported_id = body.get("model_id")
    if reported_id != expected_model_id:
        raise FaceRecognizerUnavailable(
            f"face extractor unavailable: the pinned face weights are not loaded "
            f"({role} gateway reported model_id={reported_id!r}, expected {expected_model_id!r})"
        )
    return body


async def load_face_recognizer(
    model_path: str, expected_sha256: str | None = None
) -> dict[str, Any]:
    """Build the gateway handle for the w600k_r50 embedder ([r307b])."""
    from backend.core.config import get_settings

    weights = Path(model_path)
    model_id = (
        _model_id(_RECOGNIZER_NAME, weights, expected_sha256)
        if expected_sha256
        else face_recognizer_model_id()
    )
    base_url = get_settings().enrichment_light_url
    logger.info(f"face-recognizer configured (model_id={model_id}, provider=gateway)")
    return {
        "session": _gateway_session(base_url, model_id),
        "input_name": "input.1",
        "model_id": model_id,
        "embedding_dim": FACE_EMBEDDING_DIM,
    }


async def load_face_detector(model_path: str, expected_sha256: str | None = None) -> dict[str, Any]:
    """Build the gateway handle for SCRFD-10G-KPS ([r307b])."""
    from backend.core.config import get_settings

    weights = Path(model_path)
    model_id = (
        _model_id(_DETRACTOR_NAME, weights, expected_sha256)
        if expected_sha256
        else face_detector_model_id()
    )
    base_url = get_settings().enrichment_light_url
    return {
        "session": _gateway_session(base_url, model_id),
        "input_name": "input.1",
        "model_id": model_id,
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

    resized = crop.convert("RGB").resize(FACE_INPUT_SIZE, PILImage.Resampling.BILINEAR)
    arr = np.asarray(resized, dtype=np.float32) / 127.5 - 1.0  # [0,255] -> [-1,1]
    arr = arr.transpose(2, 0, 1)[None]  # HWC -> CHW with batch dim
    return np.ascontiguousarray(arr, dtype=np.float32)


def extract_face_embedding(session: Any, crop: Image.Image) -> list[float]:
    """Embed one aligned face crop: **the** L2-normalized 512-d vector.

    When `session` is a gateway handle dict (`kind == "gateway"`), calls
    `POST {base_url}/face-recognize` ([r307b]). Also supports duck-typed
    `.run()` sessions for unit/contract tests.
    """
    import numpy as np

    if isinstance(session, dict) and session.get("kind") == "gateway":
        expected_id = str(session.get("model_id") or face_recognizer_model_id())
        body = _post_gateway(
            session,
            "face-recognize",
            {"image": _encode_image_png_b64(crop)},
            role="face-recognizer",
            expected_model_id=expected_id,
        )
        raw_vec = body.get("embedding") or []
    else:
        feed = preprocess_face_crop(crop)
        try:
            raw = session.run(None, {"input.1": feed})
        except Exception as e:
            raise FaceRecognizerError(f"face-recognizer inference failed: {e}") from e
        raw_vec = raw[0]

    vector = np.asarray(raw_vec, dtype=np.float32).reshape(-1)
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
        PILImage.fromarray(arr).resize((nw, nh), PILImage.Resampling.BILINEAR), dtype=np.float32
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

    When `session` is a gateway handle dict (`kind == "gateway"`), calls
    `POST {base_url}/face-detect` ([r307b]). Also supports duck-typed
    `.run()` sessions for unit/parity tests."""
    import numpy as np

    if isinstance(session, dict) and session.get("kind") == "gateway":
        expected_id = str(session.get("model_id") or face_detector_model_id())
        body = _post_gateway(
            session,
            "face-detect",
            {
                "image": _encode_image_png_b64(image),
                "threshold": float(threshold),
                "nms_iou": float(nms_iou),
            },
            role="face-detector",
            expected_model_id=expected_id,
        )
        out: list[ScrfdFace] = []
        for item in body.get("faces") or []:
            bx = item.get("bbox") or [0.0, 0.0, 0.0, 0.0]
            kps_raw = item.get("landmarks")
            landmarks = (
                np.asarray(kps_raw, dtype=np.float32).reshape(5, 2)
                if kps_raw is not None and len(kps_raw) == 5
                else None
            )
            out.append(
                ScrfdFace(
                    bbox=(float(bx[0]), float(bx[1]), float(bx[2]), float(bx[3])),
                    score=float(item.get("confidence", 0.0)),
                    landmarks=landmarks,
                )
            )
        return out

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
        centers = (
            np.stack(list(np.mgrid[:h, :w][::-1]), axis=-1).astype(np.float32) * stride
        ).reshape(-1, 2)
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
    return pil.transform(
        FACE_INPUT_SIZE, PILImage.Transform.AFFINE, coeffs, resample=PILImage.Resampling.BILINEAR
    )


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


# ---------------------------------------------------------------------------
# The leg as one call, for the paths that ENROLL vectors (F11 ruling 2)
# ---------------------------------------------------------------------------


def get_face_leg_handles() -> tuple[dict[str, Any], dict[str, Any]] | None:
    """The two face-leg handles (detector, recognizer).

    If `model_zoo`'s registry holds preloaded handles (e.g. in unit tests),
    returns them; otherwise returns gateway handles pointing at
    `settings.enrichment_light_url` (`/enrich-lt/face-detect` and
    `/enrich-lt/face-recognize`, [r307b]) with the `models.yml`-pinned
    `model_id` values (`face-detector-scrfd@scrfd_10g_bnkps@5838f7fe0536` and
    `face-recognizer@w600k_r50@4c06341c33c2`).
    """
    from backend.core.config import get_settings
    from backend.services.model_zoo import get_model_manager

    loaded = get_model_manager()._loaded_models
    det = loaded.get(_DETRACTOR_NAME)
    rec = loaded.get(_RECOGNIZER_NAME)
    if det is not None and rec is not None:
        return det, rec

    base_url = get_settings().enrichment_light_url
    det_id = face_detector_model_id()
    rec_id = face_recognizer_model_id()
    return (
        {
            "session": _gateway_session(base_url, det_id),
            "input_name": "input.1",
            "model_id": det_id,
        },
        {
            "session": _gateway_session(base_url, rec_id),
            "input_name": "input.1",
            "model_id": rec_id,
            "embedding_dim": FACE_EMBEDDING_DIM,
        },
    )


def passes_quality_gate(*, face_px: float, score: float, min_px: int, min_score: float) -> bool:
    """The F11 ruling 3 gate: minimum face size AND minimum SCRFD score,
    both edges inclusive (a 40-px face at 0.6 passes — the point is that
    config moves the floor, never that the floor is argued here).

    Pure: takes values, never reads Settings. Lives with the leg because
    BOTH consumers are the leg's — the specialist stage refuses to call a
    gate-failing crop "unknown", and server-side enrollment refuses to
    enroll one (an enrollment below the gate is a gallery row that can
    never honestly match). One function is what stops the two halves from
    drifting into two spaces' worth of opinions.
    """
    return face_px >= min_px and score >= min_score


def enrollment_quality(face_px: float, score: float, *, min_px: int) -> float:
    """Enrollment quality from the SAME two inputs the specialist's gate
    uses (crop size + SCRFD score) — replacing the old bbox-area heuristic,
    which "scored" a face the detector did not even find.

    Deliberately a plain, documented map rather than a face-quality model:
    CR-FIQA is the ledgered later item (F12), and until it lands the honest
    statement is "this is size and detector confidence, the gate's own
    terms". Anchored so the endpoint's bands stay reachable: a crop at
    4x ``min_px`` with a confident detection saturates at 0.95, a crop at
    the gate floor with a threshold-score detection lands mid-band.
    """
    size_term = min(1.0, face_px / (4.0 * max(min_px, 1)))
    return min(0.95, 0.5 * size_term + 0.5 * float(score))


def extract_enrollment_vector(
    image: Any,
    *,
    det_session: Any,
    rec_session: Any,
    model_id: str,
    threshold: float,
    min_px: int,
    min_score: float,
) -> tuple[list[float], float, str] | None:
    """Detect -> take the best face -> align -> embed, in one call, for the
    enrollment paths (an enrollment needs a vector AND its provenance AND a
    quality score, so the three are computed together from one detection).

    Returns ``(vector, quality, model_id)`` for the best face that clears
    the score gate, or None when the image holds no such face (a real
    observation — "enroll a picture with a visible face"). The vector is
    the same computation the specialist stage runs on a probe, so an
    enrolled vector and a probed vector share a space by construction
    (F11 ruling 2's "same loader" clause). ``model_id`` is passed through
    from the loaded handle rather than looked up again: the caller that
    resolved the handles owns the provenance claim.

    Runs the leg's own steps on the current thread — callers that care
    about the event loop (the routes do) wrap it in ``run_in_executor``.
    """
    import numpy as np

    faces = detect_faces(det_session, image, threshold=threshold)
    if not faces:
        return None
    # Best = detector confidence first, area second: the enrollment wants
    # the most trustworthy face in the frame, not merely the largest.
    best = max(
        faces, key=lambda f: (float(f.score), (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
    )
    face_px = min(best.bbox[2] - best.bbox[0], best.bbox[3] - best.bbox[1])
    if not passes_quality_gate(
        face_px=face_px, score=float(best.score), min_px=min_px, min_score=min_score
    ):
        # Below the gate the crop cannot be trusted to identify anyone, so
        # it is not offered for enrollment at all — the same rule that
        # keeps "unknown" off gate-failing probes (F11 ruling 3).
        return None
    quality = enrollment_quality(face_px, best.score, min_px=min_px)
    crop = align_face_crop(image, best.landmarks)
    vector = extract_face_embedding(rec_session, crop)
    if float(np.linalg.norm(np.asarray(vector, dtype=np.float32))) == 0.0:
        return None
    return vector, quality, model_id
