#!/usr/bin/env bash
# [r307a] Face models in Triton (SCRFD + ArcFace): the committed stage-by-stage runner (ruling 307).
#
# Mirrors scripts/uplevel/reid_real_tier.sh ([r157]):
#   Stage 1: Raw pinned ONNX (scrfd_10g_bnkps.onnx + w600k_r50.onnx) on CPU onnxruntime (reference)
#   Stage 2: Prepared ONNX (scrfd/1/model.onnx + arcface/1/model.onnx after graph surgery) on CPU onnxruntime
#   Stage 3: TensorRT model.plan (FP32) evaluated directly on the GPU
#   Stage 4: TensorRT model.plan (FP16 / default build) evaluated directly on the GPU
#   Stage 5: Gateway HTTP routes (POST /enrich-lt/face-detect and POST /enrich-lt/face-recognize)
#            served by Triton with GATEWAY_MODEL_SET=vlm and GATEWAY_ENABLE_FACE=true
#
# Gates:
#   - ArcFace cosine >= 0.999 (ruling 68's gate)
#   - SCRFD box IoU >= 0.99 and max box coordinate diff <= 1.0 px (at 640x640, 0.15% of frame)
#   - SCRFD 5 landmarks max coordinate diff <= 1.0 px
#   - Model IDs match CPU loader (face-detector-scrfd@scrfd_10g_bnkps@5838f7fe0536 and
#     face-recognizer@w600k_r50@4c06341c33c2)
#
# Usage:
#   scripts/uplevel/face_real_tier.sh --checkout <host checkout> --gpu <index> \
#       [--port N] [--weights-dir DIR] [--images DIR] [--head SHA] [--plan-timeout SECONDS]
set -euo pipefail

CHECKOUT=""
GPU=""
PORT="${FACE_TIER_PORT:-18097}"
WEIGHTS_DIR="${FACE_WEIGHTS_DIR:-/export/ai_models/model-zoo/face-recognizer}"
IMAGES=""
HEAD=""
PLAN_TIMEOUT=600
IMAGE="${FACE_TIER_IMAGE:-hsi-gateway:r307a}"
CTR="${FACE_TIER_CONTAINER:-r307a-face-gw}"

usage() {
  awk '
    NR == 1 { next }
    /^[[:space:]]*$/ { next }
    /^#/ { sub(/^# ?/, ""); print; next }
    { exit }
  ' "$0"
  exit "${1:-2}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --checkout)     CHECKOUT="$2"; shift 2 ;;
    --gpu)          GPU="$2"; shift 2 ;;
    --port)         PORT="$2"; shift 2 ;;
    --weights-dir)  WEIGHTS_DIR="$2"; shift 2 ;;
    --images)       IMAGES="$2"; shift 2 ;;
    --head)         HEAD="$2"; shift 2 ;;
    --plan-timeout) PLAN_TIMEOUT="$2"; shift 2 ;;
    -h|--help)      usage 0 ;;
    *) echo "unknown argument: $1" >&2; usage 1 ;;
  esac
done

[[ -n "$CHECKOUT" && -n "$GPU" && -n "$IMAGES" ]] || {
  echo "--checkout, --gpu, and --images are required" >&2
  usage 1
}
[[ "$GPU" =~ ^[0-9]+$ ]] || { echo "--gpu must be an index, got '$GPU'" >&2; exit 1; }
[[ "$PORT" =~ ^[0-9]+$ ]] || { echo "--port must be a number, got '$PORT'" >&2; exit 1; }
[[ "$PLAN_TIMEOUT" =~ ^[0-9]+$ && "$PLAN_TIMEOUT" -ge 1 ]] || {
  echo "--plan-timeout must be a positive number of seconds, got '$PLAN_TIMEOUT'" >&2
  exit 1
}
[[ -e "$CHECKOUT/.git" ]] || { echo "--checkout is not a git checkout: $CHECKOUT" >&2; exit 1; }

if podman container exists "$CTR"; then echo "Refusing pre-existing container $CTR" >&2; exit 1; fi
if podman image exists "$IMAGE"; then echo "Refusing pre-existing image $IMAGE" >&2; exit 1; fi

RUN="$(mktemp -d "/tmp/face-real-tier-$(date -u +%Y%m%dT%H%MZ)-XXXXXX")"
mkdir -p "$RUN/cache/scrfd/1" "$RUN/cache/arcface/1" "$RUN/cache_fp32/scrfd/1" "$RUN/cache_fp32/arcface/1" "$RUN/zoo"
echo "RUN=$RUN"

WT=0
OWN_IMAGE=0
OWN_CTR=0

snapshot_docker() {
  docker ps -aq 2>/dev/null | xargs -r docker inspect 2>/dev/null \
    --format '{{.Id}} {{.Name}} {{.State.Running}} {{.State.StartedAt}} {{.RestartCount}}' | sort
}

take_snapshot() {
  local tag="$1"
  podman ps -a --format '{{.Names}} {{.Status}} {{.StartedAt}}' > "$RUN/$tag-podman-ps.txt"
  podman volume ls -q | sort > "$RUN/$tag-podman-volumes.txt"
  if command -v docker >/dev/null 2>&1; then
    snapshot_docker > "$RUN/$tag-docker.txt"
    docker volume ls -q 2>/dev/null | sort > "$RUN/$tag-docker-volumes.txt"
  else
    : > "$RUN/$tag-docker.txt"
    : > "$RUN/$tag-docker-volumes.txt"
  fi
}

# shellcheck disable=SC2329
cleanup() {
  local rc=$?
  trap - EXIT
  set +e
  if (( OWN_CTR )); then
    podman logs "$CTR" > "$RUN/gateway.log" 2>&1
    podman rm -f "$CTR"
  fi
  if (( OWN_IMAGE )); then podman rmi "$IMAGE"; fi
  take_snapshot after
  local changed=0
  for pair in podman-ps podman-volumes docker docker-volumes; do
    if ! diff -u "$RUN/before-$pair.txt" "$RUN/after-$pair.txt" > "$RUN/diff-$pair.txt"; then
      cat "$RUN/diff-$pair.txt"
      changed=1
    fi
  done
  if (( WT )); then git -C "$CHECKOUT" worktree remove --force "$RUN/src" || rc=1; fi
  (( changed == 0 )) || rc=1
  printf '%s\n' "$rc" > "$RUN/exit-code.txt"
  echo "Outputs retained in $RUN; exit=$rc"
  exit "$rc"
}
trap cleanup EXIT

take_snapshot before

REV="${HEAD:-$(git -C "$CHECKOUT" rev-parse HEAD)}"
git -C "$CHECKOUT" worktree add --detach "$RUN/src" "$REV"
WT=1

cp -f "$WEIGHTS_DIR/scrfd_10g_bnkps.onnx" "$RUN/zoo/scrfd_10g_bnkps.onnx"
cp -f "$WEIGHTS_DIR/w600k_r50.onnx" "$RUN/zoo/w600k_r50.onnx"
chmod 0444 "$RUN/zoo/scrfd_10g_bnkps.onnx" "$RUN/zoo/w600k_r50.onnx"

cat > "$RUN/stage_probe_face.py" <<'PROBE'
"""Evaluate Stages 2 (prepared ONNX on CPU ORT), 3 (FP32 TensorRT plan), and 4 (FP16/default TensorRT plan)."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from ai.gateway.adapters.enrichment_light import (
    _SCRFD_OUTPUT_NAMES,
    _decode_scrfd_outputs,
    _scrfd_blob,
)

RUN = Path(sys.argv[1])
IMAGES_DIR = Path(sys.argv[2])
SUFFIX = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
_FACE_INPUT_SIZE = (112, 112)
_ARCFACE_TEMPLATE = (
    (38.2946, 51.6963),
    (73.5318, 51.5014),
    (56.0252, 68.4922),
    (41.5493, 92.2507),
    (70.7299, 92.4101),
)
_TRT_CACHE: dict[str, tuple[Any, Any]] = {}


def _align_face_crop(image: Image.Image, landmarks: Any) -> Image.Image:
    """5-point similarity warp onto ARCFACE_TEMPLATE (mirrors face_recognizer_loader.align_face_crop)."""
    src = np.asarray(_ARCFACE_TEMPLATE, dtype=np.float64).reshape(-1, 2)
    dst = np.asarray(landmarks, dtype=np.float64).reshape(-1, 2)
    n = src.shape[0]
    design = np.zeros((2 * n, 4), dtype=np.float64)
    design[0::2] = np.column_stack([src[:, 0], -src[:, 1], np.ones(n), np.zeros(n)])
    design[1::2] = np.column_stack([src[:, 1], src[:, 0], np.zeros(n), np.ones(n)])
    (a, b, tx, ty), *_ = np.linalg.lstsq(design, dst.reshape(-1), rcond=None)
    coeffs = (float(a), float(-b), float(tx), float(b), float(a), float(ty))
    pil = Image.fromarray(np.ascontiguousarray(np.asarray(image.convert("RGB"), dtype=np.uint8)))
    return pil.transform(
        _FACE_INPUT_SIZE, Image.Transform.AFFINE, coeffs, resample=Image.Resampling.BILINEAR
    )


def _preprocess_face_crop(crop: Image.Image) -> np.ndarray:
    """(1, 3, 112, 112) float32 NCHW RGB arr / 127.5 - 1.0 (mirrors face_recognizer_loader.preprocess_face_crop)."""
    resized = crop.convert("RGB").resize(_FACE_INPUT_SIZE, Image.Resampling.BILINEAR)
    arr = np.asarray(resized, dtype=np.float32) / 127.5 - 1.0
    return np.ascontiguousarray(arr.transpose(2, 0, 1)[np.newaxis, ...], dtype=np.float32)


def _raw_scrfd_has_face(raw_scrfd: Any, img: Image.Image, threshold: float = 0.6) -> bool:
    blob, scale = _scrfd_blob(np.asarray(img))
    outs = raw_scrfd.run(_SCRFD_OUTPUT_NAMES, {"input.1": blob})
    raw_det = dict(zip(_SCRFD_OUTPUT_NAMES, outs, strict=True))
    return bool(_decode_scrfd_outputs(raw_det, scale=scale, threshold=threshold, nms_iou=0.4))


def _trt_infer_dict(plan_path: Path, feed: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    import tensorrt as trt
    import torch

    key = str(plan_path)
    if key not in _TRT_CACHE:
        logger = trt.Logger(trt.Logger.WARNING)
        with open(plan_path, "rb") as fh:
            engine = trt.Runtime(logger).deserialize_cuda_engine(fh.read())
        if engine is None:
            raise RuntimeError(f"could not deserialize {plan_path}")
        _TRT_CACHE[key] = (engine, engine.create_execution_context())
    engine, context = _TRT_CACHE[key]
    stream = torch.cuda.current_stream().cuda_stream
    dev_tensors: dict[str, torch.Tensor] = {}
    out_names: list[str] = []
    batch_dim = 1
    for i in range(engine.num_io_tensors):
        name = engine.get_tensor_name(i)
        if engine.get_tensor_mode(name) == trt.TensorIOMode.INPUT:
            arr = np.ascontiguousarray(feed[name], dtype=np.float32)
            batch_dim = int(arr.shape[0])
            context.set_input_shape(name, arr.shape)
            t = torch.from_numpy(arr).cuda().contiguous()
            dev_tensors[name] = t
            context.set_tensor_address(name, t.data_ptr())
    for i in range(engine.num_io_tensors):
        name = engine.get_tensor_name(i)
        if engine.get_tensor_mode(name) != trt.TensorIOMode.INPUT:
            shape = tuple(
                batch_dim if int(d) <= 0 else int(d) for d in context.get_tensor_shape(name)
            )
            t = torch.empty(shape, dtype=torch.float32, device="cuda")
            dev_tensors[name] = t
            out_names.append(name)
            context.set_tensor_address(name, t.data_ptr())
    if not context.execute_async_v3(stream):
        raise RuntimeError(f"execute_async_v3 failed for {plan_path}")
    torch.cuda.synchronize()
    return {name: dev_tensors[name].cpu().numpy() for name in out_names}


def _eval_stage(
    paths: list[Path],
    scrfd_fn: Any,
    arcface_fn: Any,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for p in paths:
        img = Image.open(p).convert("RGB")
        blob, scale = _scrfd_blob(np.asarray(img))
        raw_det = scrfd_fn(blob)
        faces = _decode_scrfd_outputs(raw_det, scale=scale, threshold=0.6, nms_iou=0.4)
        if not faces:
            out.append({"name": p.name, "detected": False})
            continue
        best = max(
            faces,
            key=lambda f: (float(f.confidence), (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1])),
        )
        crop = _align_face_crop(img, best.landmarks)
        crop_blob = _preprocess_face_crop(crop)
        vec = np.asarray(arcface_fn(crop_blob), dtype=np.float32).reshape(-1)
        norm = float(np.linalg.norm(vec))
        vec_list = [float(v) for v in (vec / norm)] if norm > 0 else [0.0] * 512
        out.append(
            {
                "name": p.name,
                "detected": True,
                "bbox": list(best.bbox),
                "landmarks": [list(pt) for pt in best.landmarks],
                "embedding": vec_list,
            }
        )
    return out


def main() -> None:
    import onnxruntime as ort

    raw_scrfd = ort.InferenceSession(
        str(RUN / "zoo" / "scrfd_10g_bnkps.onnx"), providers=["CPUExecutionProvider"]
    )
    all_paths = sorted(p for p in IMAGES_DIR.iterdir() if p.suffix.lower() in SUFFIX)
    face_paths = [
        p
        for p in all_paths
        if _raw_scrfd_has_face(raw_scrfd, Image.open(p).convert("RGB"), threshold=0.6)
    ]

    prep_scrfd = ort.InferenceSession(
        str(RUN / "cache" / "scrfd" / "1" / "model.onnx"), providers=["CPUExecutionProvider"]
    )
    prep_arcface = ort.InferenceSession(
        str(RUN / "cache" / "arcface" / "1" / "model.onnx"), providers=["CPUExecutionProvider"]
    )

    def s2_scrfd(blob: np.ndarray) -> dict[str, np.ndarray]:
        outs = prep_scrfd.run(_SCRFD_OUTPUT_NAMES, {"input.1": blob})
        return dict(zip(_SCRFD_OUTPUT_NAMES, outs, strict=True))

    def s2_arcface(crop_blob: np.ndarray) -> np.ndarray:
        return prep_arcface.run(["683"], {"input.1": crop_blob})[0][0]

    stages = [
        {"stage": "2", "candidates": _eval_stage(face_paths, s2_scrfd, s2_arcface)},
        {
            "stage": "3",
            "candidates": _eval_stage(
                face_paths,
                lambda b: _trt_infer_dict(RUN / "cache_fp32" / "scrfd" / "1" / "model.plan", {"input.1": b}),
                lambda c: _trt_infer_dict(RUN / "cache_fp32" / "arcface" / "1" / "model.plan", {"input.1": c})["683"][0],
            ),
        },
        {
            "stage": "4",
            "candidates": _eval_stage(
                face_paths,
                lambda b: _trt_infer_dict(RUN / "cache" / "scrfd" / "1" / "model.plan", {"input.1": b}),
                lambda c: _trt_infer_dict(RUN / "cache" / "arcface" / "1" / "model.plan", {"input.1": c})["683"][0],
            ),
        },
    ]
    (RUN / "stages.json").write_text(json.dumps(stages, indent=2) + "\n")


if __name__ == "__main__":
    main()
PROBE

podman build -t "$IMAGE" -f "$RUN/src/ai/gateway/Dockerfile" "$RUN/src"
OWN_IMAGE=1

# Export ONNX + compile FP32 and FP16/default TensorRT plans + evaluate Stages 2/3/4
podman run --rm --device "nvidia.com/gpu=${GPU}" \
  -v "$RUN:/run-dir:z" \
  -v "$RUN/src:/src:ro,z" \
  -v "$IMAGES:/images:ro,z" \
  -e PYTHONPATH=/src \
  --entrypoint /bin/bash "$IMAGE" -c "
    set -euo pipefail
    for role_pair in 'scrfd:/run-dir/zoo/scrfd_10g_bnkps.onnx' 'arcface:/run-dir/zoo/w600k_r50.onnx'; do
      role=\${role_pair%%:*}
      src=\${role_pair#*:}
      python3 /src/ai/gateway/export/export_face.py --role \"\$role\" --model-path \"\$src\" --output-path \"/run-dir/cache/\$role/1/model.onnx\"
      cp -f \"/run-dir/cache/\$role/1/model.onnx\" \"/run-dir/cache_fp32/\$role/1/model.onnx\"
      cp -f \"/run-dir/cache/\$role/1/provenance.json\" \"/run-dir/cache_fp32/\$role/1/provenance.json\"
      python3 /src/ai/gateway/export/export_face.py --role \"\$role\" --model-path \"\$src\" --output-path \"/run-dir/cache_fp32/\$role/1/model.plan\" --precision fp32 --plan-timeout ${PLAN_TIMEOUT}
      python3 /src/ai/gateway/export/export_face.py --role \"\$role\" --model-path \"\$src\" --output-path \"/run-dir/cache/\$role/1/model.plan\" --precision fp16 --plan-timeout ${PLAN_TIMEOUT}
    done
    pip install --no-cache-dir --quiet tensorrt-cu13-bindings==11.3.0.99 2>/dev/null || true
    python3 /run-dir/stage_probe_face.py /run-dir /images
  "

VRAM_BEFORE="$(nvidia-smi --id="$GPU" --query-gpu=memory.used --format=csv,noheader,nounits | tr -d '[:space:]')"

podman run -d --name "$CTR" --device "nvidia.com/gpu=${GPU}" \
  -p "127.0.0.1:${PORT}:8090" \
  -v "$RUN/cache:/models/cache:ro,z" \
  -e GATEWAY_MODEL_SET=vlm \
  -e GATEWAY_ENABLE_FACE=true \
  "$IMAGE"
OWN_CTR=1

for _ in $(seq 1 60); do
  if curl -sf "http://127.0.0.1:${PORT}/enrich-lt/health" > "$RUN/health.json" 2>/dev/null \
    && python3 -I -c 'import json,sys; m=json.load(open(sys.argv[1])).get("models",{}); sys.exit(0 if m.get("scrfd") and m.get("arcface") else 1)' "$RUN/health.json"; then
    break
  fi
  sleep 5
done

VRAM_LOADED="$(nvidia-smi --id="$GPU" --query-gpu=memory.used --format=csv,noheader,nounits | tr -d '[:space:]')"
echo "GPU memory (MiB): before=${VRAM_BEFORE} loaded=${VRAM_LOADED} added=$((VRAM_LOADED - VRAM_BEFORE))"

uv run python "$RUN/src/scripts/face_parity_check.py" \
  --detector-weights "$RUN/zoo/scrfd_10g_bnkps.onnx" \
  --recognizer-weights "$RUN/zoo/w600k_r50.onnx" \
  --gateway-url "http://127.0.0.1:${PORT}/enrich-lt" \
  --images "$IMAGES" \
  --stage-json "$RUN/stages.json" | tee "$RUN/parity-report.txt"
