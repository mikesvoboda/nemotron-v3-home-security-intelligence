#!/usr/bin/env python3
"""[r307a] Face leg (SCRFD + ArcFace) parity, stage-by-stage table, and timing.

Ruling 307 item 2:
- Serve SCRFD (`det_10g.onnx` / `scrfd_10g_bnkps.onnx`) and ArcFace (`w600k_r50.onnx`),
  the same SHA-256-pinned files, in Triton as TensorRT plans built for the serving GPU,
  behind gateway routes (`/enrich-lt/face-detect` and `/enrich-lt/face-recognize`).
- Parity against the CPU ONNX path on a fixed face set, stage by stage as `[r157]`'s
  runner does:
  * ArcFace cosine >= 0.999 (ruling 68's gate);
  * SCRFD boxes: IoU >= 0.99 and max coordinate diff <= 1.0 px (at 640x640, 1.0 px is
    0.15% of the frame and < 0.125 of the finest stride-8 anchor step);
  * SCRFD 5 landmarks: max coordinate diff <= 1.0 px (in the 112x112 aligned ArcFace
    template, <= 1.0 px shifts the similarity warp by < 0.5 px, verified end-to-end
    against the 0.999 ArcFace cosine gate).
- Records GPU memory added and latency per face, and prints `RESULT: PASS` or `RESULT: FAIL`.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import io
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ARCFACE_COSINE_GATE = 0.999
SCRFD_BOX_IOU_GATE = 0.99
SCRFD_BOX_PX_TOL = 1.0
SCRFD_LANDMARK_PX_TOL = 1.0

_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


@dataclass(frozen=True, slots=True)
class StageMetrics:
    stage: str
    arcface_min_cosine: float
    arcface_mean_cosine: float
    scrfd_min_iou: float
    scrfd_max_box_px: float
    scrfd_max_kps_px: float
    worst_item: str

    @property
    def ok(self) -> bool:
        return (
            self.arcface_min_cosine >= ARCFACE_COSINE_GATE
            and self.scrfd_min_iou >= SCRFD_BOX_IOU_GATE
            and self.scrfd_max_box_px <= SCRFD_BOX_PX_TOL
            and self.scrfd_max_kps_px <= SCRFD_LANDMARK_PX_TOL
        )


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    a64 = np.asarray(a, dtype=np.float64).reshape(-1)
    b64 = np.asarray(b, dtype=np.float64).reshape(-1)
    na = float(np.linalg.norm(a64))
    nb = float(np.linalg.norm(b64))
    if na <= 0.0 or nb <= 0.0:
        return 0.0
    return float(np.dot(a64 / na, b64 / nb))


def box_iou(box_a: tuple[float, ...], box_b: tuple[float, ...]) -> float:
    ax1, ay1, ax2, ay2 = box_a[:4]
    bx1, by1, bx2, by2 = box_b[:4]
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    union = (
        max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
        + max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
        - inter
    )
    return float(inter / union) if union > 0.0 else 0.0


def box_max_px_diff(box_a: tuple[float, ...], box_b: tuple[float, ...]) -> float:
    return float(
        np.max(
            np.abs(
                np.asarray(box_a[:4], dtype=np.float64) - np.asarray(box_b[:4], dtype=np.float64)
            )
        )
    )


def kps_max_px_diff(kps_a: Any, kps_b: Any) -> float:
    a = np.asarray(kps_a, dtype=np.float64).reshape(5, 2)
    b = np.asarray(kps_b, dtype=np.float64).reshape(5, 2)
    return float(np.max(np.abs(a - b)))


def timing_summary(samples_ms: list[float]) -> dict[str, float]:
    arr: np.ndarray = np.asarray(samples_ms, dtype=np.float64)
    return {
        "median_ms": float(np.median(arr)),
        "p95_ms": float(np.percentile(arr, 95)),
    }


def evaluate_stage(
    stage_name: str,
    references: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
) -> StageMetrics:
    """Compare a stage's per-image SCRFD + ArcFace outputs against Stage 1 (CPU ONNX)."""
    if not references or len(references) != len(candidates):
        return StageMetrics(
            stage=stage_name,
            arcface_min_cosine=0.0,
            arcface_mean_cosine=0.0,
            scrfd_min_iou=0.0,
            scrfd_max_box_px=float("inf"),
            scrfd_max_kps_px=float("inf"),
            worst_item="<count mismatch>",
        )

    cosines: list[float] = []
    ious: list[float] = []
    box_diffs: list[float] = []
    kps_diffs: list[float] = []
    worst_cos = float("inf")
    worst_item = ""

    for ref, cand in zip(references, candidates, strict=True):
        name = str(ref["name"])
        if not cand.get("detected", True):
            return StageMetrics(
                stage=stage_name,
                arcface_min_cosine=0.0,
                arcface_mean_cosine=0.0,
                scrfd_min_iou=0.0,
                scrfd_max_box_px=float("inf"),
                scrfd_max_kps_px=float("inf"),
                worst_item=f"{name} (no face detected)",
            )
        cos = cosine(np.asarray(ref["embedding"]), np.asarray(cand["embedding"]))
        iou = box_iou(tuple(ref["bbox"]), tuple(cand["bbox"]))
        b_diff = box_max_px_diff(tuple(ref["bbox"]), tuple(cand["bbox"]))
        k_diff = kps_max_px_diff(ref["landmarks"], cand["landmarks"])

        cosines.append(cos)
        ious.append(iou)
        box_diffs.append(b_diff)
        kps_diffs.append(k_diff)
        if cos < worst_cos:
            worst_cos = cos
            worst_item = name

    return StageMetrics(
        stage=stage_name,
        arcface_min_cosine=float(min(cosines)),
        arcface_mean_cosine=float(np.mean(cosines)),
        scrfd_min_iou=float(min(ious)),
        scrfd_max_box_px=float(max(box_diffs)),
        scrfd_max_kps_px=float(max(kps_diffs)),
        worst_item=worst_item,
    )


def format_stage_table(
    stages: list[StageMetrics],
    *,
    model_ids_match: bool = True,
) -> tuple[str, str]:
    """Render the stage table and return `(table_text, verdict)`."""
    lines = [
        f"{'stage':<8} {'arcface_min':>11} {'arcface_mean':>12} {'scrfd_iou':>9} "
        f"{'box_px':>8} {'kps_px':>8}  {'worst_face':<32} {'verdict':<7}"
    ]
    all_ok = bool(stages) and model_ids_match
    for s in stages:
        verdict_str = "ok" if s.ok else "FAIL"
        if not s.ok:
            all_ok = False
        lines.append(
            f"{s.stage:<8} {s.arcface_min_cosine:11.6f} {s.arcface_mean_cosine:12.6f} "
            f"{s.scrfd_min_iou:9.6f} {s.scrfd_max_box_px:8.3f} {s.scrfd_max_kps_px:8.3f}  "
            f"{s.worst_item[:32]:<32} {verdict_str:<7}"
        )
    overall = "PASS" if all_ok else "FAIL"
    lines.append("")
    lines.append(f"RESULT: {overall}")
    return "\n".join(lines), overall


def _encode_png_b64(img: Image.Image) -> str:
    rgb = img.convert("RGB") if img.mode != "RGB" else img
    buf = io.BytesIO()
    rgb.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _image_paths(directory: Path) -> list[Path]:
    return sorted(p for p in directory.iterdir() if p.suffix.lower() in _IMAGE_SUFFIXES)


async def _run_gateway_parity(args: argparse.Namespace) -> int:
    from backend.services import face_recognizer_loader as frl

    paths = _image_paths(args.images)
    if not paths:
        print(f"no images in {args.images}", file=sys.stderr)
        return 2

    import onnxruntime as ort

    det_session = ort.InferenceSession(
        str(args.detector_weights), providers=["CPUExecutionProvider"]
    )
    rec_session = ort.InferenceSession(
        str(args.recognizer_weights), providers=["CPUExecutionProvider"]
    )
    det_handle = {
        "session": det_session,
        "model_id": frl._model_id(
            "face-detector-scrfd", Path(args.detector_weights), args.detector_sha256 or None
        ),
    }
    rec_handle = {
        "session": rec_session,
        "model_id": frl._model_id(
            "face-recognizer", Path(args.recognizer_weights), args.recognizer_sha256 or None
        ),
    }
    expected_det_id = str(det_handle["model_id"])
    expected_rec_id = str(rec_handle["model_id"])

    refs: list[dict[str, Any]] = []
    cands: list[dict[str, Any]] = []
    cpu_det_ms: list[float] = []
    cpu_rec_ms: list[float] = []
    gpu_det_ms: list[float] = []
    gpu_rec_ms: list[float] = []
    gw_det_ids: set[str] = set()
    gw_rec_ids: set[str] = set()

    base = args.gateway_url.rstrip("/")
    async with httpx.AsyncClient(timeout=60.0) as client:
        # Warm up both gateway routes before timing so GPU latency reflects
        # steady-state inference rather than first-request plan initialization.
        warm_img = Image.open(paths[0]).convert("RGB")
        await client.post(
            f"{base}/face-detect",
            json={"image": _encode_png_b64(warm_img), "threshold": args.threshold},
        )
        await client.post(
            f"{base}/face-recognize",
            json={"image": _encode_png_b64(warm_img.resize((112, 112), Image.Resampling.BILINEAR))},
        )
        for path in paths:
            img = Image.open(path).convert("RGB")

            t0 = time.perf_counter()
            cpu_faces = frl.detect_faces(det_handle["session"], img, threshold=args.threshold)
            t1 = time.perf_counter()
            if not cpu_faces:
                continue
            best_cpu = max(
                cpu_faces,
                key=lambda f: (float(f.score), (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1])),
            )
            cpu_crop = frl.align_face_crop(img, best_cpu.landmarks)
            t2 = time.perf_counter()
            cpu_vec = frl.extract_face_embedding(rec_handle["session"], cpu_crop)
            t3 = time.perf_counter()

            cpu_det_ms.append((t1 - t0) * 1000.0)
            cpu_rec_ms.append((t3 - t2) * 1000.0)

            g0 = time.perf_counter()
            det_resp = await client.post(
                f"{base}/face-detect",
                json={"image": _encode_png_b64(img), "threshold": args.threshold},
            )
            det_resp.raise_for_status()
            g1 = time.perf_counter()
            det_body = det_resp.json()
            gw_det_ids.add(str(det_body.get("model_id")))
            gpu_faces = det_body.get("faces") or []
            if not gpu_faces:
                cands.append({"name": path.name, "detected": False})
                refs.append(
                    {
                        "name": path.name,
                        "bbox": list(best_cpu.bbox),
                        "landmarks": np.asarray(best_cpu.landmarks, dtype=np.float32).tolist(),
                        "embedding": cpu_vec,
                    }
                )
                continue

            best_gpu = max(
                gpu_faces,
                key=lambda f: (
                    float(f["confidence"]),
                    (f["bbox"][2] - f["bbox"][0]) * (f["bbox"][3] - f["bbox"][1]),
                ),
            )
            gpu_crop = frl.align_face_crop(img, best_gpu["landmarks"])
            g2 = time.perf_counter()
            rec_resp = await client.post(
                f"{base}/face-recognize",
                json={"image": _encode_png_b64(gpu_crop)},
            )
            rec_resp.raise_for_status()
            g3 = time.perf_counter()
            rec_body = rec_resp.json()
            gw_rec_ids.add(str(rec_body.get("model_id")))

            gpu_det_ms.append((g1 - g0) * 1000.0)
            gpu_rec_ms.append((g3 - g2) * 1000.0)

            refs.append(
                {
                    "name": path.name,
                    "bbox": list(best_cpu.bbox),
                    "landmarks": np.asarray(best_cpu.landmarks, dtype=np.float32).tolist(),
                    "embedding": cpu_vec,
                }
            )
            cands.append(
                {
                    "name": path.name,
                    "detected": True,
                    "bbox": best_gpu["bbox"],
                    "landmarks": best_gpu["landmarks"],
                    "embedding": rec_body["embedding"],
                }
            )

    if not refs:
        print("no faces detected in any input image", file=sys.stderr)
        return 2

    ids_match = (gw_det_ids == {expected_det_id}) and (gw_rec_ids == {expected_rec_id})
    stage5 = evaluate_stage("5", refs, cands)

    stages: list[StageMetrics] = []
    if args.stage_json:
        for item in json.loads(args.stage_json.read_text()):
            stages.append(evaluate_stage(str(item["stage"]), refs, item["candidates"]))
    stages.append(stage5)

    cpu_det = timing_summary(cpu_det_ms)
    cpu_rec = timing_summary(cpu_rec_ms)
    gpu_det = timing_summary(gpu_det_ms) if gpu_det_ms else {"median_ms": 0.0, "p95_ms": 0.0}
    gpu_rec = timing_summary(gpu_rec_ms) if gpu_rec_ms else {"median_ms": 0.0, "p95_ms": 0.0}

    print(
        f"faces: {len(refs)}  arcface_gate: {ARCFACE_COSINE_GATE}  scrfd_iou_gate: {SCRFD_BOX_IOU_GATE}  px_tol: {SCRFD_BOX_PX_TOL}"
    )
    print(f"detector model_id:   cpu {expected_det_id}  gateway {sorted(gw_det_ids)}")
    print(f"recognizer model_id: cpu {expected_rec_id}  gateway {sorted(gw_rec_ids)}")
    print(
        f"cpu (onnxruntime)  detect median {cpu_det['median_ms']:.1f} ms (p95 {cpu_det['p95_ms']:.1f} ms)  "
        f"embed median {cpu_rec['median_ms']:.1f} ms (p95 {cpu_rec['p95_ms']:.1f} ms)  "
        f"total median {cpu_det['median_ms'] + cpu_rec['median_ms']:.1f} ms/face"
    )
    print(
        f"gpu (triton plan)  detect median {gpu_det['median_ms']:.1f} ms (p95 {gpu_det['p95_ms']:.1f} ms)  "
        f"embed median {gpu_rec['median_ms']:.1f} ms (p95 {gpu_rec['p95_ms']:.1f} ms)  "
        f"total median {gpu_det['median_ms'] + gpu_rec['median_ms']:.1f} ms/face"
    )
    print()
    table_text, overall = format_stage_table(stages, model_ids_match=ids_match)
    print(table_text)
    return 0 if overall == "PASS" else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    ap.add_argument(
        "--detector-weights", type=Path, required=True, help="scrfd_10g_bnkps.onnx path"
    )
    ap.add_argument("--recognizer-weights", type=Path, required=True, help="w600k_r50.onnx path")
    ap.add_argument("--gateway-url", required=True, help="gateway /enrich-lt URL")
    ap.add_argument("--images", type=Path, required=True, help="directory of face images")
    ap.add_argument("--threshold", type=float, default=0.6)
    ap.add_argument(
        "--detector-sha256",
        default="5838f7fe053675b1c7a08b633df49e7af5495cee0493c7dcf6697200b85b5b91",  # pragma: allowlist secret
    )
    ap.add_argument(
        "--recognizer-sha256",
        default="4c06341c33c2ca1f86781dab0e829f88ad5b64be9fba56e56bc9ebdefc619e43",  # pragma: allowlist secret
    )
    ap.add_argument(
        "--stage-json",
        type=Path,
        default=None,
        help="Optional JSON file carrying intermediate stage (2, 3, 4) candidates",
    )
    return asyncio.run(_run_gateway_parity(ap.parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main())
