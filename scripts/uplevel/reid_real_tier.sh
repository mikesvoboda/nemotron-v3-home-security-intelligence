#!/usr/bin/env bash
# O2.4 re-ID real tier: the committed runner (package [r157], rulings 157 + 159).
#
# This is o24.sh (the design partner's script, pinned on #7002) merged with
# o24-run-safe.sh (the script the owner's 2026-10-13 maui run actually used),
# with the four things ruling 159 makes arguments: --port, --checkpoint, --gpu,
# --crops, plus ONE sequence step restored: STEP 2b compiles the FP16 plan
# before the parity arm serves (o24-run-safe.sh compiled there; Triton's reid
# declares backend: "tensorrt" and each invocation allocates a fresh cache, so
# a parity run that never compiles has no plan to serve).
#
# Two modes:
#
#   parity (default)   #6970's command: scripts/reid_parity_check.py, the CPU
#                      reference against the gateway's served plan, every crop,
#                      cosine per crop against ruling 68's 0.999 gate. Exits 0
#                      only when every crop clears the gate AND the model IDs
#                      match. On a near-miss (0.99 <= min < 0.999) it rebuilds
#                      the plan once in FP32 and retries, exactly as
#                      o24-run-safe.sh does, so a precision loss is separated
#                      from a fault.
#
#   stages             the 5-stage diagnostic ruling 157 orders. Cosine PER CROP
#                      against the backend's CPU OSNet vector at each stage; the
#                      first stage under the gate is where parity breaks:
#                        1 PyTorch on the production checkpoint (the reference;
#                          ~1.0 by construction -- it IS stage 1)
#                        2 ONNX Runtime CPU on the exported model.onnx  -> export
#                        3 the plan, called directly, FP32              -> the plan
#                        4 the plan, called directly, FP16              -> precision only
#                        5 gateway POST /enrich-lt/person-reid          -> the binding
#
#                      Owner run 6154659954 recorded cosine min 0.230 / mean
#                      0.331 on 36 crops. A ~0.3 cosine is two unit vectors that
#                      carry RELATED-BUT-DIFFERENT features, not a destroyed
#                      image (~0.0) and not a normalisation slip (~0.9): the
#                      shape is a transform/layout fault. Stage 3 vs 4 is what
#                      that run could not do (FP32 was never tried), and it is
#                      what separates "the plan is wrong" from "FP16 is not
#                      enough".
#
# UR-133/UR-134, unchanged from o24-run-safe.sh: a fresh detached worktree at a
# named head (never the live checkout, never its .env), the port bound to
# loopback only, the model cache mounted READ-ONLY, the checkpoint copied into
# the run directory and read-only from there, the image tag local and never
# pushed, and teardown on ANY exit -- podman AND docker snapshots taken before
# the first change and diffed after the last, so a leak fails the run instead of
# hiding in someone's `ps`.
#
# Usage:
#   scripts/uplevel/reid_real_tier.sh --checkout <host checkout> --gpu <index> \
#       [--port N] [--checkpoint DIR] [--crops DIR] [--head SHA] [--mode parity|stages] \
#       [--plan-timeout SECONDS]
#
# With no --crops the runner stops after build/export/compile and prints the run
# directory: populate <run>/crops and `touch <run>/crops-ready` (the owner's flow
# from o24-run-safe.sh, kept because real camera crops cannot be synthesised -- a
# synthetic crop would pass the parity check it is meant to test, the same trap
# as a hand-written junit row).
#
# On the GPU host (maui), the owner's command is the whole contract; this runner
# reproduces it with a named head and an argument for every host path. Stages 3
# and 4 call the TensorRT plan directly using ai/common/tensorrt_utils.py's own
# binding idiom (torch CUDA tensors bound by device pointer), so they exercise
# the SAME plan the Triton tensorrt backend loads, not a reimplementation of it.
set -euo pipefail

# --- arguments -------------------------------------------------------------------------

CHECKOUT=""
GPU=""
PORT="${REID_TIER_PORT:-18099}"
CHECKPOINT="${ZOO_SRC:-/export/ai_models/model-zoo/osnet-ain-x1-0}"
CROPS=""
HEAD=""
MODE="parity"
# Wall-clock bound forwarded to export_reid's ONE trtexec build. Ruling 180 keeps
# 600 as the default on purpose (the same FP16 command built in 137.7 s on
# 2026-10-13, so a ten-minute build is the failure the owner wants to SEE);
# --plan-timeout lifts it for a run expected to be slow on a contended GPU.
PLAN_TIMEOUT=600
IMAGE="${REID_TIER_IMAGE:-hsi-gateway:b22}"
CTR="${REID_TIER_CONTAINER:-b22-reid-gw}"
# models.yml `osnet-ain-x1-0.runtime_file`; the sha256 it pins is read from
# models.yml at run time below, so the runner can never test bytes the loader
# would refuse.
WEIGHTS_FILE="osnet_ain_x1_0_msmt17.pth"

usage() {
  # The header comment IS the help text, so it cannot drift from it. The header
  # block ends at the first line that is neither blank nor a comment, which is
  # why the in-body `# --- section ---` banners never print. Line 1 is the
  # shebang, not prose, so it is skipped.
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
    --checkout)   CHECKOUT="$2"; shift 2 ;;
    --gpu)        GPU="$2"; shift 2 ;;
    --port)       PORT="$2"; shift 2 ;;
    --checkpoint)   CHECKPOINT="$2"; shift 2 ;;
    --crops)        CROPS="$2"; shift 2 ;;
    --head)         HEAD="$2"; shift 2 ;;
    --mode)         MODE="$2"; shift 2 ;;
    --plan-timeout) PLAN_TIMEOUT="$2"; shift 2 ;;
    -h|--help)      usage 0 ;;
    *) echo "unknown argument: $1" >&2; usage 1 ;;
  esac
done

[[ -n "$CHECKOUT" && -n "$GPU" ]] || { echo "--checkout and --gpu are required" >&2; usage 1; }
[[ "$MODE" == parity || "$MODE" == stages ]] || { echo "--mode is parity or stages" >&2; usage 1; }
[[ "$GPU" =~ ^[0-9]+$ ]] || { echo "--gpu must be an index, got '$GPU'" >&2; exit 1; }
[[ "$PORT" =~ ^[0-9]+$ ]] || { echo "--port must be a number, got '$PORT'" >&2; exit 1; }
[[ "$PLAN_TIMEOUT" =~ ^[0-9]+$ && "$PLAN_TIMEOUT" -ge 1 ]] || { echo "--plan-timeout must be a positive number of seconds, got '$PLAN_TIMEOUT'" >&2; exit 1; }
[[ -e "$CHECKOUT/.git" ]] || { echo "--checkout is not a git checkout: $CHECKOUT" >&2; exit 1; }
# UR-133: the runner never touches the live stack. It gets its own worktree, its
# own port and a read-only weights copy, and refuses rather than sharing anything.

# --- refusal + free-port checks (from o24-run-safe.sh) -----------------------------------

if podman container exists "$CTR"; then echo "Refusing pre-existing container $CTR" >&2; exit 1; fi
if podman image exists "$IMAGE"; then echo "Refusing pre-existing image $IMAGE" >&2; exit 1; fi
if ! python3 -I - "$PORT" <<'PY'
import socket, sys
port = int(sys.argv[1])
s = socket.socket()
try:
    s.bind(("127.0.0.1", port))
except OSError as exc:
    sys.exit(f"port {port} is not free on loopback: {exc}")
finally:
    s.close()
PY
then
  echo "Refusing to start: the loopback port is busy (the live gateway holds 18090)" >&2
  exit 1
fi

# --- run directory ---------------------------------------------------------------------

RUN="$(mktemp -d "/tmp/reid-real-tier-$(date -u +%Y%m%dT%H%MZ)-XXXXXX")"
printf '%s\n' "$RUN" > /tmp/reid-real-tier-current-run.txt
mkdir -p "$RUN/cache/reid/1" "$RUN/crops" "$RUN/zoo"
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

# --- teardown: runs on ANY exit, and a leak makes the run fail -------------------------

# shellcheck disable=SC2329 # invoked indirectly: registered as `trap cleanup EXIT` below
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
    echo "== diff $pair"
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
trap 'exit 130' INT
trap 'exit 143' TERM

take_snapshot before

# --- a fresh tree at a named head (UR-133) ---------------------------------------------

BRANCH="${REID_TIER_BRANCH:-uplevel/r157-o24-reid-parity}"
# The branch is fetched on EVERY path, not only when --head is absent. Fetching in
# one arm only was a trap: `worktree add` on a sha the host has never seen dies
# with `invalid reference`, and o24.sh's own note warns that a pinned sha goes stale
# on every roll -- so a named head has to be checked for and fetched into the
# checkout, not assumed to be there because it was read off the PR page.
git -C "$CHECKOUT" fetch origin "$BRANCH"
if [[ -z "$HEAD" ]]; then
  HEAD="$(git -C "$CHECKOUT" rev-parse FETCH_HEAD)"
else
  git -C "$CHECKOUT" cat-file -e "$HEAD^{commit}" 2>/dev/null \
    || git -C "$CHECKOUT" fetch --quiet origin "$HEAD" >/dev/null 2>&1 || true
  git -C "$CHECKOUT" cat-file -e "$HEAD^{commit}" 2>/dev/null || {
    echo "--head $HEAD is not an object in $CHECKOUT (fetching $BRANCH did not" >&2
    echo "bring it in, and a direct fetch of the sha was refused or failed)." >&2
    echo "Run: git -C $CHECKOUT fetch origin $HEAD   -- or drop --head to use the" >&2
    echo "live $BRANCH head." >&2
    exit 1
  }
fi
printf '%s\n' "$HEAD" > "$RUN/commit.txt"
echo "head=$HEAD (report this sha with the result)"
git -C "$CHECKOUT" worktree add --detach "$RUN/src" "$HEAD"
WT=1
# A fresh tree must carry no live secrets. Checked, not assumed: o24-run-safe.sh
# proved this by inspection once, and an unguarded .env would put real LAN
# credentials into a container built to be throwaway.
[[ ! -e "$RUN/src/.env" && ! -L "$RUN/src/.env" ]] || {
  echo "fresh tree unexpectedly contains .env; refusing" >&2
  exit 1
}

# --- weights, copied read-only INTO the run directory ------------------------------------

# o24.sh mounted the model-zoo path directly; o24-run-safe.sh copies instead, so the
# run is independent of whether /export/ai_models exists on this host. Copied, then
# bind-mounted read-only: nothing the container does can write the zoo.
[[ -d "$CHECKPOINT" ]] || { echo "checkpoint dir not found: $CHECKPOINT" >&2; exit 1; }
cp -L "$CHECKPOINT/$WEIGHTS_FILE" "$RUN/zoo/$WEIGHTS_FILE"
chmod a=r "$RUN/zoo/$WEIGHTS_FILE"
# models.yml is copied INTO the image at build; read the pin from the tree the
# image was built from so the pin and the bytes are always the same head's.
PIN_SHA="$(git -C "$RUN/src" show HEAD:models.yml \
  | python3 -I -c 'import re, sys
m = re.search(r"name: osnet-ain-x1-0.*?sha256: ([0-9a-f]{64})", sys.stdin.read(), re.S)
print(m.group(1) if m else "")')"
[[ -n "$PIN_SHA" ]] || { echo "could not read the osnet sha256 pin from models.yml" >&2; exit 1; }
echo "$PIN_SHA  $RUN/zoo/$WEIGHTS_FILE" | sha256sum -c -
sha256sum "$RUN/zoo/$WEIGHTS_FILE" > "$RUN/checkpoint-sha256.txt"

nvidia-smi --query-gpu=index,name,memory.used,memory.total --format=csv | tee "$RUN/gpu-before.txt"

# --- 1. build this head's gateway image (local tag, never pushed) ----------------------

echo 'STEP 1: build'
OWN_IMAGE=1
podman build --no-cache -f "$RUN/src/ai/gateway/Dockerfile" -t "$IMAGE" "$RUN/src" \
  > "$RUN/build.log" 2>&1

# --- 2. ONNX export from the production checkpoint --------------------------------------

echo 'STEP 2: ONNX export'
# --network none and the read-only zoo: export needs neither network nor write.
podman run --rm --network none --security-opt label=disable --entrypoint python3 \
  -v "$RUN/zoo":/zoo:ro -v "$RUN/cache":/out \
  "$IMAGE" -m ai.gateway.export.export_reid \
    --model-path "/zoo/$WEIGHTS_FILE" --output-path /out/reid/1/model.onnx \
  > "$RUN/export.log" 2>&1
cat "$RUN/cache/reid/1/provenance.json"

compile_plan() {
  # Writes beside the ONNX (Triton's fixed 1/model.plan) and refuses, inside
  # export_reid, unless the provenance record vouches for these exact bytes.
  #
  # Ruling 180 item 3: every build stamps its own wall time and a compute-apps
  # snapshot into $RUN before it starts. gpu-before.txt cannot serve this purpose
  # -- it is a one-shot memory total taken before the FIRST build and names no
  # PID, so it cannot answer the question the owner's maui run actually raised
  # ("GPU 0 at 100% throughout": slow build, or someone else's process on the
  # card?). --query-compute-apps is the only nvidia-smi query that names the
  # tenants; it goes to its own file per precision so the FP32 and FP16 legs are
  # read separately. Wall time is stamped HERE, not read from trtexec's output,
  # because a build killed by the bound never gets to print a duration.
  local precision="$1"
  local ts
  ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  {
    echo "precision=$precision start=$ts plan_timeout=${PLAN_TIMEOUT}s"
    nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv || true
  } > "$RUN/compute-apps-$precision.txt" 2>&1
  local started=$SECONDS
  # `|| rc=$?` rather than a bare command: the failing build must not abort the
  # function under `set -e` before the elapsed-time line lands, and the same
  # wrapper runs in parity (a bare, fatal call) and in stages (contained by the
  # caller's `&& cp … || true`). Returning the status explicitly keeps the
  # witness write unconditional while the caller still sees the real rc.
  local rc=0
  podman run --rm --network none --security-opt label=disable --device nvidia.com/gpu=all \
    -e CUDA_VISIBLE_DEVICES="$GPU" --entrypoint python3 \
    -v "$RUN/zoo":/zoo:ro -v "$RUN/cache":/out \
    "$IMAGE" -m ai.gateway.export.export_reid \
      --model-path "/zoo/$WEIGHTS_FILE" --output-path /out/reid/1/model.plan \
      --precision "$precision" --plan-timeout "$PLAN_TIMEOUT" \
    > "$RUN/compile-$precision.log" 2>&1 || rc=$?
  echo "precision=$precision elapsed=$(( SECONDS - started ))s rc=$rc" \
    >> "$RUN/compute-apps-$precision.txt"
  return "$rc"
}

# --- crops: real camera frames only -----------------------------------------------------

if [[ -n "$CROPS" ]]; then
  cp -L "$CROPS"/* "$RUN/crops"/ 2>/dev/null || true
  : > "$RUN/crops-ready"
fi

if [[ ! -f "$RUN/crops-ready" ]]; then
  echo "AWAITING_REAL_CROPS: put at least 30 person crops (one person per image,"
  echo "cut from real camera frames) in $RUN/crops, then: touch $RUN/crops-ready"
  ready=0
  for (( i = 0; i < 1800; i++ )); do
    [[ -f "$RUN/crops-ready" ]] && { ready=1; break; }
    sleep 1
  done
  (( ready )) || { echo "real-camera crops were not supplied" >&2; exit 1; }
fi

python3 -I - "$RUN/crops" <<'PY'
from pathlib import Path
import sys
SUFFIX = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
p = Path(sys.argv[1])
images = [x for x in p.iterdir() if x.is_file() and x.suffix.lower() in SUFFIX]
assert len(images) >= 30, f"need at least 30 real crops, found {len(images)}"
print("real-camera crop files:", len(images))
PY

# --- the gateway: loopback, read-only cache, threat off -----------------------------------

GATEWAY="http://127.0.0.1:$PORT/enrich-lt"

start_gateway() {
  OWN_CTR=1
  # UR-134 is unconditional: a test deployment ALWAYS runs with
  # ORCHESTRATOR_ENABLED=false. Nothing in this image reads it today -- the
  # gateway image COPYs only ai/gateway and ai/triton (the two COPY lines that
  # name them in ai/gateway/Dockerfile), and the flag's sole reader is backend/core/config.py -- so omitting it
  # was inert, not unsafe. It is set anyway: the rule is not conditional on the
  # image happening to lack the code, and a container that later gains the
  # backend must not inherit an orchestrator-enabled default from this script.
  podman run -d --name "$CTR" --security-opt label=disable \
    -p "127.0.0.1:$PORT:8090" \
    --device nvidia.com/gpu=all -e CUDA_VISIBLE_DEVICES="$GPU" \
    -e GATEWAY_MODEL_SET=vlm -e GATEWAY_ENABLE_THREAT=false \
    -e ORCHESTRATOR_ENABLED=false \
    -v "$RUN/cache":/models/cache:ro "$IMAGE"
  local healthy=0
  for (( i = 0; i < 60; i++ )); do
    if curl -fsS --max-time 5 "$GATEWAY/health" > "$RUN/health.json" 2>/dev/null \
      && python3 -I -c 'import json,sys; sys.exit(0 if json.load(open(sys.argv[1]))["models"]["reid"] else 1)' \
         "$RUN/health.json"; then
      healthy=1; break
    fi
    sleep 5
  done
  if (( ! healthy )); then
    podman logs "$CTR" | tail -n 50
    echo "reid never came up (health checked at models.reid, not a string match)" >&2
    return 1
  fi
  # Ruling 157 bullet 2 wants the binding printed "as they are bound", and stage
  # 5's suspect IS the Triton binding (header: tensor names, [3,256,128] layout,
  # batch). Triton's HTTP port 8000 is NOT published to the host (only 8090 is,
  # on loopback), so read it from INSIDE the container and save it: this is
  # Triton's own view of reid's input/output names, dims and data types, which is
  # what the gateway's adapter binds against. Non-fatal by design -- a missing
  # curl in the image must not fail a parity run whose real job is the cosine --
  # but it prints loudly when absent so the posted run shows the gap.
  if podman exec "$CTR" sh -c 'curl -fsS localhost:8000/v2/models/reid/config' \
      > "$RUN/triton-reid-config.json" 2>/dev/null; then
    echo 'triton reid config (Triton bound names/shapes as the gateway serves them):'
    python3 -I - "$RUN/triton-reid-config.json" <<'TRT'
import json, sys
d = json.load(open(sys.argv[1]))
print("  input :", [(i["name"], i["datatype"], i["shape"]) for i in d.get("input", [])])
print("  output:", [(o["name"], o["datatype"], o["shape"]) for o in d.get("output", [])])
TRT
  else
    echo "WARN: could not read Triton's reid config (no curl in the image?); the stage-5 binding print is missing -- the plan-side print in the probe still stands"
  fi
  # An earlier owner run timed out on FIRST inference (plan load is lazy). Warm up
  # before anything measures time, or the timings are the load, not the model.
  python3 -I - "$RUN" "$GATEWAY" <<'PY'
import base64, json, sys, urllib.request
from pathlib import Path
SUFFIX = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
run = Path(sys.argv[1])
crop = next(x for x in sorted((run / "crops").iterdir()) if x.suffix.lower() in SUFFIX)
body = json.dumps({"image": base64.b64encode(crop.read_bytes()).decode()}).encode()
req = urllib.request.Request(
    sys.argv[2] + "/person-reid", data=body, headers={"Content-Type": "application/json"}
)
with urllib.request.urlopen(req, timeout=180) as response:
    (run / "warmup-response.json").write_bytes(response.read())
print("warmup ok:", sys.argv[2] + "/person-reid")
PY
}

# --- stages mode: the ruling-157 diagnostic ---------------------------------------------

# The probe runs INSIDE the image, so torch/onnx/onnxruntime/tensorrt are the
# serving image's own versions -- measuring a parity failure against a different
# torch than the one that serves is measuring the wrong thing. Stages 1-2 need no
# GPU; stages 3-4 dlopen the plan the same way the Triton tensorrt backend does,
# using ai/common/tensorrt_utils.py's binding idiom (device pointers, set by
# name) rather than a reimplementation. Stage 5 runs on the HOST, not the
# container: the gateway is published on the host's loopback, and a container on
# its own network namespace cannot reach it.
write_stage_probe() {
  cat > "$RUN/stage_probe.py" <<'PROBE'
"""Per-crop re-ID embeddings, one file per stage, for the O2.4 diagnostic.

Reads every crop in the run dir and writes ``stage-<n>.json`` holding
{names: [...], vectors: [[512 floats], ...]}. The runner then takes a per-crop
cosine against stage 1. Stage 1 is the reference BY CONSTRUCTION (it is the same
PyTorch checkpoint the backend loads), which is the point: every other stage is
measured against the thing the parity gate actually protects.

Preprocessing here is the gateway adapter's OWN transform
(ai/gateway/adapters/enrichment_light.py:225-230: resize (128,256) BILINEAR, /255,
ImageNet mean/std, transpose CHW). Stage 1 still uses the adapter's transform --
not the backend's torchvision Resize -- on purpose: if stage 1 and stage 2 agree
under THIS transform but the real parity check fails, the fault is that the two
production transforms (adapter BILINEAR vs torchvision Resize) diverge, and that
shows up only at stage 5. Keeping every stage on one transform isolates the graph
from the preprocessing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

RUN = Path(sys.argv[1])
STAGES = sys.argv[2].split(",")
SUFFIX = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

CROPS = sorted(x for x in (RUN / "crops").iterdir() if x.is_file() and x.suffix.lower() in SUFFIX)
if not CROPS:
    raise SystemExit("no crops found")


def _preprocess(path: Path) -> np.ndarray:
    from PIL import Image

    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    img = Image.open(path).convert("RGB").resize((128, 256), Image.Resampling.BILINEAR)
    arr = np.asarray(img, dtype=np.float32) / 255.0
    arr = (arr - mean) / std
    return np.ascontiguousarray(arr.transpose(2, 0, 1))


BATCH = np.stack([_preprocess(p) for p in CROPS]).astype(np.float32)
NAMES = [p.name for p in CROPS]
WEIGHTS_FILE = "osnet_ain_x1_0_msmt17.pth"


def stage_pytorch() -> np.ndarray:
    import torch

    from ai.gateway.export.export_reid import MAX_BATCH, load_pytorch_model

    model = load_pytorch_model(str(RUN / "zoo" / WEIGHTS_FILE))
    model.eval()
    out = []
    with torch.no_grad():
        for i in range(0, len(BATCH), MAX_BATCH):
            out.append(model(torch.from_numpy(BATCH[i : i + MAX_BATCH])).float().numpy())
    return np.concatenate(out)


def stage_onnx_cpu() -> np.ndarray:
    import onnxruntime as ort

    sess = ort.InferenceSession(
        str(RUN / "cache" / "reid" / "1" / "model.onnx"),
        providers=["CPUExecutionProvider"],  # explicit: the image ships ORT-GPU
    )
    return sess.run(["embedding"], {"input": BATCH})[0]


def _trt_run(plan: Path) -> np.ndarray:
    """Run the plan directly, per the repo's own TensorRT idiom.

    Mirrors ai/common/tensorrt_utils.py:663-698 -- inputs and outputs are torch
    CUDA *device* tensors bound by their data_ptr (a numpy host pointer is NOT a
    device address; TRT would read garbage), tensors bound by NAME so a rename
    surfaces as a missing name, dynamic batch set per chunk, and one
    execute_async_v3 on the current torch stream.
    """
    import tensorrt as trt
    import torch

    from ai.gateway.export.export_reid import MAX_BATCH

    logger = trt.Logger(trt.Logger.WARNING)
    with open(plan, "rb") as fh:  # nosemgrep: path-traversal-open
        engine = trt.Runtime(logger).deserialize_cuda_engine(fh.read())
    if engine is None:
        raise SystemExit(f"could not load {plan}")
    context = engine.create_execution_context()
    # Enumerated the way ai/common/tensorrt_utils.py:269-273 does -- by index
    # over num_io_tensors, then get_tensor_name/get_tensor_mode -- not by
    # iterating the engine object, which is not that API.
    in_names, out_names = [], []
    for i in range(engine.num_io_tensors):
        name = engine.get_tensor_name(i)
        if engine.get_tensor_mode(name) == trt.TensorIOMode.INPUT:
            in_names.append(name)
        else:
            out_names.append(name)
    if len(in_names) != 1 or len(out_names) != 1:
        raise SystemExit(f"expected 1 in / 1 out tensor, got in={in_names} out={out_names}")
    # The output width comes from the PLAN, not from a constant we assume: a plan
    # whose declared embedding width disagrees with export_reid's is exactly the
    # kind of layout fault this diagnostic exists to find, so name it instead of
    # writing into a wrongly-sized buffer. A dynamic (-1) width falls back to the
    # exporter's own constant.
    from ai.gateway.export.export_reid import EMBEDDING_DIM

    declared = int(engine.get_tensor_shape(out_names[0])[-1])
    if declared <= 0:
        declared = EMBEDDING_DIM
    if declared != EMBEDDING_DIM:
        raise SystemExit(
            f"{plan} declares a {declared}-wide output but export_reid expects "
            f"{EMBEDDING_DIM}; refusing to compare across different widths"
        )

    # Ruling 157 bullet 2 names this output as a stage-3/4 DELIVERABLE, not a
    # debug aid: "with Triton's input and output names, shapes and layout printed
    # as they are bound." Stage 5's suspect IS the binding (the header: tensor
    # names, [3,256,128] layout, batch), and a CHW-vs-transposed fault is
    # shape- and dtype-legal -- invisible to the cosine until the owner can
    # EYEBALL what the plan actually asks for against what the probe feeds. So
    # read the metadata back off the engine and print it, per precision, right
    # here, before a single byte is bound. get_tensor_mode/get_tensor_shape/
    # get_tensor_dtype are the engine's OWN view, not a reimplementation of it.
    def _io(name: str) -> str:
        return (
            f"{name}[mode={engine.get_tensor_mode(name).name} "
            f"declared={tuple(engine.get_tensor_shape(name))} "
            f"dtype={engine.get_tensor_dtype(name).name}]"
        )

    print(f"plan {plan.name}: binding as the engine sees it")
    print(f"  engine input : {_io(in_names[0])}")
    print(f"  engine output: {_io(out_names[0])}")
    print(
        f"  probe feeds   : shape {tuple(BATCH.shape)} dtype {BATCH.dtype} "
        "layout NCHW (adapter transform: resize (128,256) BILINEAR, /255, ImageNet mean/std)"
    )
    out = np.empty((len(BATCH), declared), dtype=np.float32)
    stream = torch.cuda.current_stream().cuda_stream
    for i in range(0, len(BATCH), MAX_BATCH):
        chunk = BATCH[i : i + MAX_BATCH]
        n = chunk.shape[0]
        context.set_input_shape(in_names[0], chunk.shape)
        dev_in = torch.from_numpy(np.ascontiguousarray(chunk)).cuda().contiguous()
        dev_out = torch.empty((n, declared), dtype=torch.float32, device="cuda")
        context.set_tensor_address(in_names[0], dev_in.data_ptr())
        context.set_tensor_address(out_names[0], dev_out.data_ptr())
        if not context.execute_async_v3(stream):
            raise SystemExit(f"execute_async_v3 failed on {plan} at row {i}")
        torch.cuda.synchronize()
        out[i : i + n] = dev_out.cpu().numpy()
    return out


def stage_plan(precision: str) -> np.ndarray:
    # NO fallback to cache/reid/1/model.plan. That file is whatever
    # compile_plan wrote LAST, and run_stages compiles fp32 THEN fp16, so the
    # cache copy is the FP16 plan. A stage-3 that fell back would therefore
    # measure the FP16 plan and report it as FP32 clean -- silently re-creating
    # the exact question this diagnostic exists to answer (FP32 vs FP16 is the
    # only thing separating "the plan is wrong" from "FP16 is not enough").
    # A missing per-precision plan must fail the stage; the cosine table then
    # prints `unknown` for it, and finding 3 makes that exit non-zero.
    plan = RUN / f"model-{precision}.plan"
    if not plan.is_file():
        raise SystemExit(
            f"stage {precision} has no {plan.name}; refusing to fall back to the "
            f"cache plan (that file is the LAST compiled precision, so a fallback "
            "could measure the wrong plan and report it as this one)"
        )
    return _trt_run(plan)


BUILDERS = {
    "1": stage_pytorch,
    "2": stage_onnx_cpu,
    "3": lambda: stage_plan("fp32"),
    "4": lambda: stage_plan("fp16"),
}

for stage in STAGES:
    vectors = BUILDERS[stage]()
    (RUN / f"stage-{stage}.json").write_text(
        json.dumps({"names": NAMES, "vectors": [[float(x) for x in v] for v in vectors]})
    )
    print(f"stage {stage}: {len(vectors)} x {np.asarray(vectors).shape[1]}")
PROBE
}

# Stage 5 runs on the host: base64 the crop, POST, read the embedding. Stdlib only,
# so it runs on the GPU host's plain python3 with the SAME crop ordering the in-image
# probe used (identical sort + suffix set), which keeps the per-crop cosine honest.
write_stage5_host() {
  cat > "$RUN/stage5_host.py" <<'PY5'
"""Stage 5: embeddings from the served gateway, one per crop, on the host."""
import base64
import json
import sys
import urllib.request
from pathlib import Path

RUN = Path(sys.argv[1])
GATEWAY = sys.argv[2]
SUFFIX = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
CROPS = sorted(x for x in (RUN / "crops").iterdir() if x.is_file() and x.suffix.lower() in SUFFIX)
names, vectors = [], []
for path in CROPS:
    body = json.dumps({"image": base64.b64encode(path.read_bytes()).decode()}).encode()
    req = urllib.request.Request(
        GATEWAY + "/person-reid", data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=180) as response:
        vectors.append(json.loads(response.read())["embedding"])
    names.append(path.name)
(RUN / "stage-5.json").write_text(json.dumps({"names": names, "vectors": vectors}))
print(f"stage 5: {len(vectors)} x {len(vectors[0]) if vectors else 0}")
PY5
}

# The cosine table is pure stdlib so it runs on the host with no numpy, reading the
# JSON the in-image probe wrote. First stage under the gate is the fault's location.
write_cosine_table() {
  cat > "$RUN/cosine_table.py" <<'TABLE'
import json
import math
import sys
from pathlib import Path

GATE = 0.999
run = Path(sys.argv[1])


def load(n):
    f = run / f"stage-{n}.json"
    if not f.is_file():
        return None
    d = json.loads(f.read_text())
    return d["names"], [list(map(float, v)) for v in d["vectors"]]


def cosine(a, b):
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return sum(x * y for x, y in zip(a, b)) / (na * nb)


ref = load("1")
if ref is None:
    raise SystemExit("stage 1 (the PyTorch reference) is missing; nothing to compare to")
names, refv = ref
print(f"{'stage':6} {'min':>9} {'mean':>9}  {'worst crop':40}  verdict")
first = None
unknown = []
for stage in "2345":
    got = load(stage)
    if got is None:
        print(f"{stage:6} {'-':>9} {'-':>9}  {'(probe unavailable - see the step log)':40}  unknown")
        unknown.append(stage)
        continue
    gnames, v = got
    if gnames != names:
        print(f"{stage:6} {'-':>9} {'-':>9}  {'(crop order differs from stage 1)':40}  unknown")
        unknown.append(stage)
        continue
    cos = [cosine(r, w) for r, w in zip(refv, v)]
    lo = min(range(len(cos)), key=lambda i: cos[i])
    ok = min(cos) >= GATE
    print(f"{stage:6} {min(cos):9.6f} {sum(cos)/len(cos):9.6f}  {names[lo][:40]:40}  "
          f"{'ok' if ok else 'FIRST FAILURE'}")
    if not ok and first is None:
        first = stage
print()
if first is None and not unknown:
    print("RESULT: no stage below the 0.999 gate - the diagnostic found nothing to find")
elif first is None:
    print(f"RESULT: INCONCLUSIVE - stages {'+'.join(unknown)} never produced vectors")
else:
    print(f"RESULT: the first stage under the gate is {first}")
    print({
        "2": "the ONNX export changed the graph (export_reid / op folding)",
        "3": "the plan itself is wrong, independent of precision (build flag, or a layout the plan bakes in)",
        "4": "precision only - FP32 was clean, so the fix is a build flag, not a preprocessing change",
        "5": "the BINDING: tensor names, [3,256,128] layout, batch, or the adapter's preprocessing",
    }[first])
    if unknown:
        print(f"  (stages {'+'.join(unknown)} were also unreadable; {first} is the first MEASURED failure)")
# An unknown row is a leg that never ran, not a verdict. The owner runs this
# diagnostic ONCE on maui and posts that one run, so a headline and an exit code
# that both read clean while three legs are dead is the failure mode this table
# must not have: `|| true` on the legs is deliberate (a raising stage leaves its
# JSON absent rather than killing the run), so the only place that can see the
# gap is here. Exit 2 = the diagnostic was INCOMPLETE. That is kept distinct
# from a located first failure, which stays exit 0: naming the broken stage IS
# this mode succeeding, so it must not share an exit status with "nothing ran".
if unknown:
    sys.exit(2)
TABLE
}

run_stages() {
  write_stage_probe
  echo 'STEP S1+S2: PyTorch reference and ONNX Runtime CPU (no GPU needed)'
  # /work is read-WRITE because the probe writes stage-<n>.json there, but the two
  # paths it only READS are re-mounted :ro on top of it, so UR-134's read-only
  # weights and cache hold here too. (Nested mounts: the more specific path wins.)
  # The probe imports ai.gateway.* from the image's own /app -- COPY'd from $RUN/src
  # at this head -- so it runs the head's code with no source mount, and no -I,
  # because isolated mode would drop the image's ENV PYTHONPATH=/app.
  # Each stage is fault-tolerant: a stage that raises just leaves its JSON absent
  # and the cosine table reports `unknown`, never a false green.
  podman run --rm --network none --security-opt label=disable --entrypoint python3 \
    -v "$RUN":/work -v "$RUN/zoo":/work/zoo:ro -v "$RUN/cache":/work/cache:ro \
    "$IMAGE" /work/stage_probe.py /work 1,2 || true

  # STEP S3, the ruling-180 shape: build and probe EACH precision before
  # touching the other. The owner's maui run showed why the old order was wrong:
  # it compiled FP32 (130.9 s, good), copied it, then compiled FP16 — which hit
  # the 600 s bound, and under `set -euo pipefail` that abort ended the run
  # before stage 3 was ever probed. The FP32 measurement the whole diagnostic
  # exists to take ("separates 'the plan is wrong' from 'FP16 is not enough'",
  # ruling 157) was already on disk, unprobed. The AND-chain is load-bearing in
  # BOTH directions: `|| true` contains a failed build so its stage just leaves
  # its JSON absent (the table prints `unknown`, finding 3 fails the run), and
  # the `&&` means a plan is only ever copied from a build that reported
  # success. Both precisions write the SAME cache path
  # ($RUN/cache/reid/1/model.plan), so a copy taken after an unsuccessful build
  # can only ever capture the other precision's bytes. A build that dies
  # mid-compilation is the common case and is handled one frame down:
  # export_reid.py unlinks its own half-written engine (:828 for a timeout,
  # :831 for a non-zero builder), so the cache then holds NO plan and a bare
  # `cp` would only print a confusing ENOENT. The failure this `&&` actually
  # guards is the one that raises BEFORE any build starts — export_reid.py
  # :1009-1017 keeps that path from unlinking on purpose, because output_path
  # may be the plan a gateway is serving right now. The cache then still holds
  # FP32's bytes, and an unconditional copy would mint model-fp16.plan out of
  # them and have stage 4 measure FP32 reporting it as FP16 — the wrong-plan
  # swap stage_plan refuses to fall back over. Chaining costs nothing and
  # covers both shapes.
  echo 'STEP S3a: compile the plan in FP32 and probe stage 3 (before FP16 can fail)'
  compile_plan fp32 && cp "$RUN/cache/reid/1/model.plan" "$RUN/model-fp32.plan" || true
  podman run --rm --network none --security-opt label=disable --device nvidia.com/gpu=all \
    -e CUDA_VISIBLE_DEVICES="$GPU" --entrypoint python3 \
    -v "$RUN":/work -v "$RUN/zoo":/zoo:ro \
    "$IMAGE" /work/stage_probe.py /work 3 || true

  echo 'STEP S3b: compile the plan in FP16 and probe stage 4 (leaves the cache on FP16)'
  compile_plan fp16 && cp "$RUN/cache/reid/1/model.plan" "$RUN/model-fp16.plan" || true
  podman run --rm --network none --security-opt label=disable --device nvidia.com/gpu=all \
    -e CUDA_VISIBLE_DEVICES="$GPU" --entrypoint python3 \
    -v "$RUN":/work -v "$RUN/zoo":/zoo:ro \
    "$IMAGE" /work/stage_probe.py /work 4 || true

  echo 'STEP S5: the served gateway (host-side HTTP: a container cannot reach host loopback)'
  # Contained, and it is load-bearing that this is the LAST line that can abort
  # the function: the gateway serves cache/reid/1/model.plan, the path BOTH
  # compiles write, so a failed FP16 build leaves it holding NO plan (the build
  # unlinks its own half-written engine). start_gateway then polls 300 s, never
  # sees models.reid healthy, and returns 1 -- and a BARE call here, under
  # `set -euo pipefail`, aborts run_stages before cosine_table.py runs, reprint-
  # ing the exact ruling-180 loss one line later: stage 3 measured, no table.
  # `|| true` is not a suppression -- the stage-5 HTTP call below is already
  # contained, a stage with no vectors reads `unknown`, and that makes the table
  # exit 2, so an incomplete diagnostic still cannot post as a clean run. The
  # unhealthy container is reaped by the EXIT trap (start_gateway set OWN_CTR=1
  # before polling), so this is the same teardown footprint as the happy path.
  start_gateway || true
  python3 -I "$RUN/stage5_host.py" "$RUN" "$GATEWAY" || true

  echo
  # The table's exit code is the run's verdict, so capture it the way the parity
  # arm captures reid_parity_check.py's: rc must reach the script's final
  # `exit "${rc:-0}"` (and so the EXIT trap's reported exit=) instead of
  # aborting under set -e before the after-snapshot and gpu-after-test.txt land.
  # Exit 2 means a stage read `unknown` -- a leg that never ran -- see the table.
  set +e
  python3 -I "$RUN/cosine_table.py" "$RUN"
  rc=$?
  set -e
}

# --- parity mode: #6970's command -------------------------------------------------------

run_parity() {
  (cd "$RUN/src" && taskset -c 0,1 uv run python scripts/reid_parity_check.py \
    --weights "$RUN/zoo" --gateway-url "$GATEWAY" --crops "$RUN/crops") 2>&1 \
    | tee "$RUN/parity.txt"
}

# --- run --------------------------------------------------------------------------------

case "$MODE" in
  parity)
    echo "STEP 2b: compile the FP16 plan the gateway will serve"
    # o24-run-safe.sh did this before serving, and it is load-bearing: the
    # cache is a fresh mktemp dir every invocation and Triton's reid declares
    # backend: "tensorrt", so without this line parity mounts a read-only
    # cache holding only model.onnx and the gateway has no plan to load.
    compile_plan fp16
    echo "STEP 3: serve and warm up"
    start_gateway
    echo 'STEP 4: fp16 parity and timings'
    set +e
    run_parity
    rc=$?
    set -e
    cp "$RUN/parity.txt" "$RUN/parity-fp16.txt"
    # A near-miss is a precision question, not a fault: rebuild once in FP32 and
    # retry before calling it a FAIL (o24-run-safe.sh's rule, kept verbatim).
    if (( rc != 0 )) && grep -q '^RESULT: FAIL' "$RUN/parity.txt" \
      && python3 -I - "$RUN/parity.txt" <<'PY'
import re, sys
s = open(sys.argv[1]).read()
m = re.search(r"^cosine: min ([0-9.]+)", s, re.M)
sys.exit(0 if m and 0.99 <= float(m.group(1)) < 0.999 else 1)
PY
    then
      echo 'cosine just under the gate: retrying the plan once in fp32'
      podman logs "$CTR" > "$RUN/gateway-fp16.log" 2>&1
      podman rm -f "$CTR"
      OWN_CTR=0
      cp "$RUN/cache/reid/1/model.plan" "$RUN/model-fp16.plan"
      compile_plan fp32
      start_gateway
      set +e
      run_parity
      rc=$?
      set -e
      cp "$RUN/parity.txt" "$RUN/parity-fp32.txt"
    fi
    ;;
  stages)
    write_stage5_host
    write_cosine_table
    run_stages
    ;;
esac

nvidia-smi --query-gpu=index,memory.used,memory.total --format=csv > "$RUN/gpu-after-test.txt"
exit "${rc:-0}"
