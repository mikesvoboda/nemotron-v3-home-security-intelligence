#!/usr/bin/env bash
# B2.3 Re-ID model bake-off real-tier runner (ruling 107, ruling 333).
#
# Evaluates OSNet-AIN x1.0 (incumbent) against the three ruling-333 challengers
# through O2.4's TensorRT path on the owner's labelled person-crop set:
#   1. osnet_ain_x1_0 (512-d, MIT, Hugging Face kaiyangzhou/osnet)
#   2. clip_reid_vit_b_16 (1280-d, MIT, Syliz517/CLIP-ReID MSMT17 ViT-B-16_60.pth)
#   3. tao_swin_tiny_256 (256-d, NVIDIA Model EULA, NGC deployable_v1.0)
#   4. tao_swin_base_1024 (1024-d, NVIDIA Model EULA, NGC deployable_v1.0)
#
# Usage:
#   scripts/uplevel/b23_real_tier.sh --checkout <host checkout> --gpu <index> \
#       --work-dir <host b23 work dir with crops/ and labels.json> \
#       [--zoo-dir DIR] [--head SHA] [--plan-timeout SECONDS]
set -euo pipefail

CHECKOUT=""
GPU=""
WORK_DIR=""
ZOO_DIR=""
HEAD=""
PLAN_TIMEOUT=600
IMAGE="${B23_TIER_IMAGE:-hsi-gateway:b23}"

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
    --work-dir)     WORK_DIR="$2"; shift 2 ;;
    --zoo-dir)      ZOO_DIR="$2"; shift 2 ;;
    --head)         HEAD="$2"; shift 2 ;;
    --plan-timeout) PLAN_TIMEOUT="$2"; shift 2 ;;
    -h|--help)      usage 0 ;;
    *) echo "unknown argument: $1" >&2; usage 1 ;;
  esac
done

[[ -n "$CHECKOUT" && -n "$GPU" && -n "$WORK_DIR" ]] || {
  echo "--checkout, --gpu, and --work-dir are required" >&2
  usage 1
}
[[ -f "$WORK_DIR/labels.json" && -d "$WORK_DIR/crops" ]] || {
  echo "--work-dir must contain labels.json and crops/ (see docs/uplevel/roles/b23-labelling-guide.md)" >&2
  exit 1
}

RUN="$(mktemp -d "/tmp/b23-real-tier-$(date -u +%Y%m%dT%H%MZ)-XXXXXX")"
ZOO="${ZOO_DIR:-$RUN/zoo}"
mkdir -p "$ZOO" "$RUN/cache"
echo "RUN=$RUN"

WT=0
OWN_IMAGE=0

cleanup() {
  local rc=$?
  trap - EXIT
  set +e
  if (( OWN_IMAGE )); then podman rmi "$IMAGE" >/dev/null 2>&1 || true; fi
  if (( WT )); then git -C "$CHECKOUT" worktree remove --force "$RUN/src" || rc=1; fi
  printf '%s\n' "$rc" > "$RUN/exit-code.txt"
  echo "Outputs retained in $RUN; exit=$rc"
  exit "$rc"
}
trap cleanup EXIT

REV="${HEAD:-$(git -C "$CHECKOUT" rev-parse HEAD)}"
git -C "$CHECKOUT" worktree add --detach "$RUN/src" "$REV"
WT=1

# 1. Fetch all 4 checkpoints with no login and verify SHA-256 (ruling 333 item 3)
uv run python "$RUN/src/scripts/b23_reid_bakeoff.py" fetch --zoo-dir "$ZOO"

if ! podman image exists "$IMAGE"; then
  podman build -t "$IMAGE" -f "$RUN/src/ai/gateway/Dockerfile" "$RUN/src"
  OWN_IMAGE=1
fi

cat > "$RUN/eval_b23_gpu.py" <<'PROBE'
"""Export, compile TensorRT plans, check ORT->TRT parity, and benchmark all 4 models on labels.json."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import onnxruntime as ort
from PIL import Image

from ai.gateway.export import export_reid
from scripts import b23_reid_bakeoff as b23

RUN = Path(sys.argv[1])
ZOO = Path(sys.argv[2])
WORK = Path(sys.argv[3])
PLAN_TIMEOUT = int(sys.argv[4])


def _trt_infer_crops(
    plan_path: Path,
    crops: list[Path],
    spec: b23.ModelSpec,
) -> tuple[dict[str, list[float]], list[float], float]:
    try:
        import tensorrt as trt
    except ModuleNotFoundError:
        import tensorrt_bindings as trt  # type: ignore[no-redef]
    import torch

    logger = trt.Logger(trt.Logger.WARNING)
    with open(plan_path, "rb") as fh:
        engine = trt.Runtime(logger).deserialize_cuda_engine(fh.read())
    if engine is None:
        raise RuntimeError(f"could not deserialize {plan_path}")
    context = engine.create_execution_context()
    stream = torch.cuda.current_stream().cuda_stream

    # Warm up once before timing
    warm_arr = b23.preprocess_crop(crops[0], spec)
    context.set_input_shape("input", warm_arr.shape)
    d_in = torch.from_numpy(warm_arr).cuda().contiguous()
    d_out = torch.empty((1, spec.embedding_dim), dtype=torch.float32, device="cuda")
    context.set_tensor_address("input", d_in.data_ptr())
    context.set_tensor_address("embedding", d_out.data_ptr())
    context.execute_async_v3(stream)
    torch.cuda.synchronize()

    embeddings: dict[str, list[float]] = {}
    latencies_ms: list[float] = []
    for p in crops:
        arr = b23.preprocess_crop(p, spec)
        t0 = time.perf_counter()
        context.set_input_shape("input", arr.shape)
        t_in = torch.from_numpy(arr).cuda().contiguous()
        t_out = torch.empty((1, spec.embedding_dim), dtype=torch.float32, device="cuda")
        context.set_tensor_address("input", t_in.data_ptr())
        context.set_tensor_address("embedding", t_out.data_ptr())
        if not context.execute_async_v3(stream):
            raise RuntimeError(f"execute_async_v3 failed for {plan_path}")
        torch.cuda.synchronize()
        vec = t_out.cpu().numpy().reshape(-1)
        t1 = time.perf_counter()
        latencies_ms.append((t1 - t0) * 1000.0)
        norm = float(np.linalg.norm(vec))
        embeddings[p.name] = [float(x) for x in (vec / norm)] if norm > 0 else [0.0] * len(vec)

    vram_mib = int(round(torch.cuda.max_memory_allocated() / (1024 * 1024)))
    return embeddings, latencies_ms, float(vram_mib)


def main() -> None:
    labels_doc = json.loads((WORK / "labels.json").read_text(encoding="utf-8"))
    crop_paths = [WORK / "crops" / str(row["crop_id"]) for row in labels_doc["crops"]]

    models_out: list[dict[str, Any]] = []
    for key, spec in b23.MODEL_SPECS.items():
        m_dir = RUN / "cache" / key / "1"
        m_dir.mkdir(parents=True, exist_ok=True)
        src_p = ZOO / spec.filename
        onnx_p = m_dir / "model.onnx"
        plan_p = m_dir / "model.plan"

        if key == "osnet_ain_x1_0":
            export_reid.main(["--model-path", str(src_p), "--output-path", str(onnx_p)])
            export_reid.main(
                [
                    "--model-path",
                    str(src_p),
                    "--output-path",
                    str(plan_p),
                    "--precision",
                    "fp16",
                    "--plan-timeout",
                    str(PLAN_TIMEOUT),
                ]
            )
        else:
            b23.main(["export", "--role", key, "--model-path", str(src_p), "--output-path", str(onnx_p)])
            b23.main(
                [
                    "export",
                    "--role",
                    key,
                    "--model-path",
                    str(src_p),
                    "--output-path",
                    str(plan_p),
                    "--precision",
                    "fp16",
                    "--plan-timeout",
                    str(PLAN_TIMEOUT),
                ]
            )

        # Verify CPU ORT vs TensorRT plan parity on first 8 crops (>= 0.999 gate)
        ort_sess = ort.InferenceSession(str(onnx_p), providers=["CPUExecutionProvider"])
        embs, lats, vram_mib = _trt_infer_crops(plan_p, crop_paths, spec)
        cosines: list[float] = []
        for p in crop_paths[: min(8, len(crop_paths))]:
            arr = b23.preprocess_crop(p, spec)
            ort_v = ort_sess.run(["embedding"], {"input": arr})[0].reshape(-1)
            ort_v = ort_v / max(float(np.linalg.norm(ort_v)), 1e-12)
            trt_v = np.asarray(embs[p.name], dtype=np.float64)
            cosines.append(float(np.dot(ort_v, trt_v)))

        models_out.append(
            {
                "model_key": key,
                "parity_min_cosine": float(min(cosines)) if cosines else 1.0,
                "vram_mib": int(vram_mib),
                "latency_ms": lats,
                "embeddings": embs,
            }
        )

    (RUN / "runs.json").write_text(json.dumps({"models": models_out}, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
PROBE

podman run --rm --device "nvidia.com/gpu=${GPU}" \
  -v "$RUN:/run-dir:z" \
  -v "$ZOO:/zoo:ro,z" \
  -v "$WORK_DIR:/work-dir:ro,z" \
  -v "$RUN/src:/src:ro,z" \
  -e PYTHONPATH=/src \
  --entrypoint /bin/bash "$IMAGE" -c "
    set -euo pipefail
    pip install --no-cache-dir --quiet tensorrt==11.3.0.99
    python3 /run-dir/eval_b23_gpu.py /run-dir /zoo /work-dir ${PLAN_TIMEOUT}
  "

uv run python "$RUN/src/scripts/b23_reid_bakeoff.py" score \
  --labels "$WORK_DIR/labels.json" \
  --runs-json "$RUN/runs.json" | tee "$RUN/bakeoff-report.md"
echo "RESULT: PASS"
