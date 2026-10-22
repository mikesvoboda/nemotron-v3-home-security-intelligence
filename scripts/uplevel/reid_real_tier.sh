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
#   layercompare       [r312a] (ruling 312): the stages sequence plus the
#                      layer-by-layer read of WHERE the ONNX->TensorRT plan
#                      diverges. The box text names Polygraphy; polygraphy is
#                      absent from the image and the repo (and the probe
#                      container runs --network none), so the compare is
#                      implemented from what the image already carries -- the
#                      same onnx graph rewrite marks every layer's output as a
#                      graph output, the decomposed graph runs under ONNX
#                      Runtime (CPU), and the TensorRT FP32 plan runs the same
#                      marked batch per layer through the engine's debug
#                      tensor API -- on the same 36 crops. Prints the FIRST
#                      layer under 0.999 cosine with its op type and name.
#                      Also adds a probe stage (6): the decomposed ONNX
#                      served through Triton's onnxruntime backend on the GPU
#                      (CUDA execution provider) from a runner-written
#                      single-model repository in its own container -- a
#                      probe only; the served repository and residency set
#                      are untouched.
#
# --triton-image REF: the Triton base image to build the gateway from
#                      ([r312a] box 2). Empty (default) builds the
#                      Dockerfile's own default (ARG TRITON_IMAGE,
#                      ai/gateway/Dockerfile:1); the two operator runs pass
#                      26.01-py3 and the latest supported release explicitly,
#                      and on the latest release the runner rebuilds the plan
#                      with THAT release's TensorRT (the exporter reads the
#                      image's own TRT_VERSION) before the stage table and
#                      the layer compare.
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
#       [--port N] [--checkpoint DIR] [--crops DIR] [--head SHA] [--mode parity|stages|layercompare] \
#       [--plan-timeout SECONDS] [--triton-image REF]
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
# [r312a]: the Triton base image, threaded to the Dockerfile's own ARG
# (TRITON_IMAGE, ai/gateway/Dockerfile:1). EMPTY default: the Dockerfile's
# default is the single place the current release lives, so the runner never
# restates it -- an empty value OMITS --build-arg entirely and today's
# behaviour is unchanged; the two operator runs pass 26.01-py3 and the latest
# supported release explicitly.
TRITON_IMAGE="${REID_TIER_TRITON_IMAGE:-}"
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
    --triton-image) TRITON_IMAGE="$2"; shift 2 ;;
    -h|--help)      usage 0 ;;
    *) echo "unknown argument: $1" >&2; usage 1 ;;
  esac
done

[[ -n "$CHECKOUT" && -n "$GPU" ]] || { echo "--checkout and --gpu are required" >&2; usage 1; }
[[ "$MODE" == parity || "$MODE" == stages || "$MODE" == layercompare ]] || { echo "--mode is parity or stages or layercompare" >&2; usage 1; }
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
  # The ORT probe container is reaped alongside the gateway. Its own launch is
  # `--rm`-guarded (podman removes it at container exit), but that only fires
  # when the CONTAINER exits -- a run killed between launch and teardown would
  # otherwise leak it and fail the run with a confusing diff about a container
  # the run itself launched. Reaping it here first makes the diff honest.
  # Guarded on OWN_CTR: the probe's name is derived from $CTR, and the same
  # external-container case that spares the gateway spares the probe.
  if (( OWN_CTR )); then
    podman rm -f "${CTR}-ortprobe" >/dev/null 2>&1 || true
  fi
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
# [r312a]: --triton-image threads the Dockerfile's ARG TRITON_IMAGE
# ([r312b]'s parameterised base); empty means the flag is OMITTED so the
# Dockerfile's own default stands. On the latest supported release this is
# what puts THAT release's TensorRT/ORT inside the image the exporter and the
# probes run on -- the image env carries TRT_VERSION (11.3.0.99 on 26.09-py3,
# 10.14.1.48+cuda13.0 on 26.01-py3), which export_reid reads to drop --fp16
# on TRT >= 11.
podman build --no-cache ${TRITON_IMAGE:+--build-arg TRITON_IMAGE="$TRITON_IMAGE"} \
  -f "$RUN/src/ai/gateway/Dockerfile" -t "$IMAGE" "$RUN/src" \
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
# Stage 6 is NOT in BUILDERS: the probe container's port is not published and
# the stage-probe container runs --network none with no podman inside it, so
# stage 6 cannot be fetched from here. The fetch lives on the HOST
# (write_stage6_host below): the runner process owns podman and the probe's
# container name, so only the host can `podman exec` into the probe. STAGES
# 1..4 loop here; stage 6's stage-6.json is written host-side and the cosine
# table reads it the same way as every other stage.

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
# Stage 6 (below) shares that host-side shape for the same reason: the runner
# process is the only thing that can exec into the probe container.
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

# Stage 6 runs on the host too: the probe container's port is NOT published (the
# same topology as the served Triton's 8000), so the only way to reach it is
# `podman exec` -- and podman lives on the host, not inside the stage-probe
# container (--network none). One exec'd PURE program does the whole leg: the
# runner feeds it the SAME batch the decomposer's faithfulness gate ate and the
# measure half rebuilds (identical crops, order and transform -- batch.json is
# written by the SAME in-image batch build that writes batch.npy), it POSTs
# each row to the probe's own loopback, and writes stage-6.json in the SAME
# {names, vectors} shape every other stage file uses, so the cosine table reads
# it with no special-casing. Stdlib only, so it runs on the GPU host's plain
# python3 -I, like stage 5 and the table. The probe's container name arrives as
# argv (the runner owns it); no env coupling.
write_stage6_host() {
  cat > "$RUN/stage6_host.py" <<'PY6'
"""Stage 6: embeddings from the ORT-probe Triton container, fetched host-side."""
import json
import subprocess
import sys

RUN = sys.argv[1]
PROBE = sys.argv[2]

# The infer program the probe container exec's. It is deliberately PURE: the
# probe container mounts ONLY its model repository, so rows arrive on stdin
# (fed by the host runner) and embeddings leave on stdout. The infer body is a
# FLAT row-major data list (Triton's HTTP infer protocol: row-major values; a
# (3,256,128) row through .tolist() nests and float() over the nested lists
# raises TypeError).
inner = (
    "import json,sys,urllib.request;"
    "rows=json.load(sys.stdin);"
    "out=[];"
    "\nfor r in rows:\n"
    '  req=urllib.request.Request("http://localhost:8000/v2/models/reid-ort/infer",'
    'data=json.dumps({"inputs":[{"name":"input","shape":[1,3,256,128],"datatype":"FP32","data":r}],'
    '"outputs":[{"name":"embedding"}]}).encode(),'
    'headers={"Content-Type":"application/json"});'
    "emb=json.loads(urllib.request.urlopen(req,timeout=120).read())['outputs'][0]['data'];"
    "out.append(emb)\n"
    "json.dump(out,sys.stdout)"
)
# The rows: the SAME batch.npy the decomposer's faithfulness gate ate and the
# measure half rebuilds -- batch.json is written by the batch build itself (the
# in-image program that also writes batch.npy), so crops, order and transform
# cannot drift from it. Read with stdlib json: the host has no numpy guarantee.
with open(f"{RUN}/layercompare/batch.json") as fh:
    batch = json.load(fh)
names, rows = batch["names"], batch["rows"]
if len(names) != len(rows) or not rows:
    raise SystemExit(f"batch.json is malformed: {len(names)} names, {len(rows)} rows")
proc = subprocess.run(
    ["podman", "exec", "-i", PROBE, "python3", "-c", inner],
    input=json.dumps(rows), capture_output=True, text=True, check=False, timeout=600,
)
if proc.returncode != 0 or not proc.stdout.strip():
    raise SystemExit(
        f"the ORT probe fetch failed (rc={proc.returncode}): "
        f"{proc.stderr.strip()[:400]}"
    )
vectors = json.loads(proc.stdout)
if len(vectors) != len(names):
    raise SystemExit(
        f"the probe returned {len(vectors)} embeddings for {len(names)} crops "
        "-- the fetch wrote stage-6.json for NO stage (a partial table would "
        "read as a measured leg)"
    )
with open(f"{RUN}/stage-6.json", "w") as fh:
    json.dump({"names": names, "vectors": vectors}, fh)
print(f"stage 6: {len(vectors)} x {len(vectors[0]) if vectors else 0}")
PY6
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
arm6 = (run / "stage6-armed").is_file()  # the [r312a] ORT-probe leg (layercompare mode only)
for stage in "2345" + ("6" if arm6 else ""):
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
        "6": "the ORT-probe leg: embeddings through Triton's onnxruntime backend (decomposed graph, GPU)",
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
  # Stage 6 is fetched host-side (write_stage6_host) when the layercompare arm
  # armed the probe: stages 1,2 always run here, stage 6's leg rides in the arm
  # below -- stages mode never arms it, so the same run_stages serves both modes.
  podman run --rm --network none --security-opt label=disable --entrypoint python3 \
    -v "$RUN":/work -v "$RUN/zoo":/work/zoo:ro -v "$RUN/cache":/work/cache:ro \
    "$IMAGE" /work/stage_probe.py /work 1,2 || true
  if [[ -f "$RUN/stage6-armed" ]]; then
    # The stage-6 fetch: host-side (the runner process owns podman), its rc is
    # contained -- a failed fetch leaves stage-6.json absent and the table reads
    # unknown, it does not abort the arm under set -e before the layer report.
    python3 -I "$RUN/stage6_host.py" "$RUN" "${CTR}-ortprobe" || true
  fi

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

# --- layercompare mode: [r312a] (ruling 312) ---------------------------------------------
#
# The stages sequence, then the layer-by-layer read of WHERE the plan diverges.
# Polygraphy is named in the box text but exists nowhere in the image or the
# repo, and the probe container runs --network none, so the compare is built
# from what the image already carries (onnx, onnxruntime, tensorrt):
#
#   * the DECOMPOSED graph, never a rewrite of the cache ONNX: the decomposer
#     rewrites its target IN PLACE (decompose_instance_norm.py tmp.replace),
#     and the cache's model.onnx is what stage 2 measures and what both
#     operator runs must share. So the compare stages its own COPY under
#     $RUN/layercompare/ and decomposes that.
#   * the decomposer's OWN exit codes gate the compare: 0 continues; 30 (the
#     rewrite moved the graph's own function), 31 (structural refusal) and 32
#     (sidecar still needed) STOP the compare -- a graph with no faithful
#     decomposition has no layer table to print.
#   * every layer's output marked: the marked graph rewrites the decomposed
#     ONNX so each intermediate tensor is ALSO a graph output, then it is run
#     under ORT CPU and under a diagnostic FP32 plan built from that same
#     marked graph (trtexec via export_reid's own builder — an existing plan
#     cannot expose per-layer outputs, and extra outputs do not change the
#     layer compute, so per-layer divergence attribution stays valid). One ORT
#     pass, one TRT pass, per-output per-crop cosine; rows go to layers.json
#     at the run root (the report half reads them there).
#   * the report is pure stdlib, like cosine_table.py, so it is CPU-testable:
#     it prints the FIRST layer under 0.999 cosine with its op type and name,
#     or the clean reading.
#
# The probe stage (6): the decomposed ONNX served through Triton's
# onnxruntime backend on the GPU (CUDA execution provider), "as a probe
# only". Its own container, its own model name (reid-ort), its own
# single-model repository written under $RUN: the served repository is baked
# into the image, entrypoint §0c only links cache dirs whose repo config
# already exists and §0d's residency prune MOVES non-set models out, so a
# probe model in the served repository would be an ai/triton edit (cell A's
# files, UR-9) plus a served-footprint change. The probe's port is NOT
# published to the host; its embeddings are fetched from inside the
# container. A failed probe leaves its stage unknown -- the table exits 2 --
# and never blocks the layer report.

# The mode's whole sequence lives in ONE function so the pinned reads see it:
# copy -> batch -> decompose (its own exit codes) -> the ORT probe (stage 6,
# contained) -> run_stages (the stage table, now with its 6 row) -> the marked
# measure -> the report. The stage-6 leg runs BEFORE run_stages because the
# table is what prints stage 6's row; the marked measure follows the FP32 plan
# copy (STEP S3a), the artifact it reads.
run_layercompare() {
  write_stage_probe
  write_stage5_host
  write_stage6_host
  write_cosine_table
  write_layer_compare
  # The compare operates on its own COPY of the export: the decomposer
  # rewrites its target IN PLACE (tmp.replace(model)), and the cache's
  # model.onnx is what stage 2 measures and what both operator runs must
  # share, so the in-place rewrite must never land on it.
  mkdir -p "$RUN/layercompare"
  cp "$RUN/cache/reid/1/model.onnx" "$RUN/layercompare/model.onnx"
  # The export may externalize initializers to a relative model.onnx.data
  # beside the proto (export_reid.py does: 217 of 251 inits on the measured
  # export). The decomposer's first read onnx.load(str(model)) resolves that
  # relative location against the TARGET's directory, so the target copy
  # needs the sidecar too -- its absence is a crash (rc 1, the module's
  # unmapped code), the failure Run 1 died on before any surgery.
  if [[ -f "$RUN/cache/reid/1/model.onnx.data" ]]; then
    cp "$RUN/cache/reid/1/model.onnx.data" "$RUN/layercompare/model.onnx.data"
  fi
  # The decomposer's pre-surgery snapshot is a DIRECTORY holding model.onnx
  # (+ sidecar), staged separately from the target -- the module refuses a
  # pre-dir that aliases the target (same inode), so a distinct directory is
  # not a nicety.
  mkdir -p "$RUN/layercompare/pre"
  cp "$RUN/cache/reid/1/model.onnx" "$RUN/layercompare/pre/model.onnx"
  if [[ -f "$RUN/cache/reid/1/model.onnx.data" ]]; then
    cp "$RUN/cache/reid/1/model.onnx.data" "$RUN/layercompare/pre/model.onnx.data"
  fi
  # The batch: the stage probe's own transform (resize (128,256) BILINEAR,
  # /255, ImageNet mean/std, CHW) over the run's crops, built INSIDE the image
  # so the very code the stage probe uses produces these bytes. numpy comes
  # from the image (probe deps), PIL too; -I is not passed so the image's
  # ENV PYTHONPATH=/app still resolves ai.gateway.*.
  podman run --rm --network none --security-opt label=disable --entrypoint python3 \
    -v "$RUN":/work \
    "$IMAGE" -c "$BATCH_PROG" > "$RUN/layercompare/batch.log" 2>&1 || true
  if [[ ! -s "$RUN/layercompare/batch.npy" ]]; then
    echo "layercompare: no batch could be built from $RUN/crops -- see layercompare/batch.log" >&2
    return 1
  fi
  # The decomposer, invoked by ITS OWN entry point so the repo's pinned exit
  # codes (0/30/31/32) govern: 0 continues; 30/31/32 stop the compare. The
  # ONLY writable mount is the layercompare directory itself -- the in-place
  # rewrite (tmp.replace) cannot reach the cache ONNX or anything else, which
  # is the isolation the mount spec states, not just a comment's promise.
  local drc=0
  podman run --rm --network none --security-opt label=disable --entrypoint python3 \
    -v "$RUN/src":/src:ro -v "$RUN/layercompare":/layercompare \
    "$IMAGE" /src/scripts/decompose_instance_norm.py \
      /layercompare/model.onnx /layercompare/pre \
      /layercompare/batch.npy /layercompare/decompose.json \
    > "$RUN/layercompare/decompose.log" 2>&1 || drc=$?
  echo "decompose rc=$drc" >> "$RUN/layercompare/decompose.log"
  if (( drc != 0 )); then
    # 30/31/32 are the module's MAPPED refusals (a graph the rewrite moved,
    # structurally refused, or whose sidecar is still needed); any other rc is
    # the module crashing -- both stop the compare. No layer table may print
    # for a graph whose decomposition is not faithful.
    echo "layercompare: the decomposer refused (rc=$drc; mapped 0/30/31/32) --" >&2
    echo "no faithful decomposed graph, so no layer table; see layercompare/decompose.log" >&2
    return "$drc"
  fi
  # Box 2's probe stage FIRST (before run_stages): the stage table is what
  # prints stage 6's row, and its cosine_table.py reads run/stage-6.json. The
  # probe is contained -- a container that never comes up leaves the row
  # unknown (the table exits 2) and never aborts the run.
  mkdir -p "$RUN/ortprobe/reid-ort/1"
  cp "$RUN/layercompare/model.onnx" "$RUN/ortprobe/reid-ort/1/model.onnx"
  cat > "$RUN/ortprobe/reid-ort/config.pbtxt" <<'ORTCFG'
name: "reid-ort"
backend: "onnxruntime"
max_batch_size: 16

input [
  {
    name: "input"
    data_type: TYPE_FP32
    dims: [ 3, 256, 128 ]
  }
]

output [
  {
    name: "embedding"
    data_type: TYPE_FP32
    dims: [ 512 ]
  }
]

instance_group [
  {
    count: 1
    kind: KIND_GPU
    gpus: [ 0 ]
  }
]
ORTCFG
  # The probe container: tritonserver as the entrypoint (NOT the gateway's
  # entrypoint.sh -- the served repository's link precondition and residency
  # prune are not a probe's), its own repository mounted at the standard
  # path, the port NOT published to the host (stage_probe's stage-6 fetch
  # reaches it with podman exec). `|| true` on the launch: a probe that never
  # comes up leaves its stage unknown, it does not abort the run.
  podman run -d --name "${CTR}-ortprobe" --rm --security-opt label=disable \
    --device nvidia.com/gpu=all -e CUDA_VISIBLE_DEVICES="$GPU" \
    -v "$RUN/ortprobe":/models/repository:ro \
    --entrypoint tritonserver "$IMAGE" \
    --model-repository=/models/repository --http-port=8000 \
    --model-control-mode=none --strict-model-config=false --exit-on-error=false \
    > "$RUN/ortprobe/container-id.txt" 2>&1 || true
  local ready=0
  for (( i = 0; i < 60; i++ )); do
    if podman exec "${CTR}-ortprobe" curl -fsS localhost:8000/v2/health/ready >/dev/null 2>&1; then
      ready=1; break
    fi
    sleep 2
  done
  if (( ! ready )); then
    echo "WARN: the onnxruntime probe never came up; stage 6 reads unknown" >&2
    podman logs "${CTR}-ortprobe" 2>/dev/null | tail -n 20 || true
    podman rm -f "${CTR}-ortprobe" >/dev/null 2>&1 || true
  fi
  touch "$RUN/stage6-armed"
  # The stages sequence EXACTLY as run_stages does it -- same compiles, same
  # probes, same containment -- with the table carrying the 6 row. run_stages
  # captures its own table rc into `rc` the way the parity arm captures the
  # parity check's.
  run_stages
  local stage_rc=$rc
  # The marked measure only reads what STEP S3a left behind (run_stages
  # above): the per-precision copies. Assert the FP32 one EXISTS before the
  # measure runs -- its absence means stage 3 never measured, and the layer
  # table would otherwise be printed over a run whose FP32 leg never ran.
  [[ -f "$RUN/model-fp32.plan" ]] || {
    echo "layercompare: model-fp32.plan was never copied (stage 3 never measured) -- no layer table" >&2
    return 1
  }
  write_layer_compare
  # The measure half runs IN-IMAGE (onnx, onnxruntime, tensorrt, the same
  # GPU visibility the plan builds use); the report half runs on the HOST in
  # --I (stdlib only, like the stage table). ONE program, two halves: the
  # measure writes run/layers.json, the report reads it.
  podman run --rm --network none --security-opt label=disable --device nvidia.com/gpu=all \
    -e CUDA_VISIBLE_DEVICES="$GPU" --entrypoint python3 \
    -v "$RUN":/work \
    "$IMAGE" /work/layer_compare.py /work --measure \
    > "$RUN/layercompare/measure.log" 2>&1 || true
  # The report is the box-1 deliverable, printed whether or not the measure
  # half survived (a dead measure is the unknown-leg shape: the report exits
  # 2 on absent rows). Captured like the stage table's rc.
  set +e
  python3 -I "$RUN/layer_compare.py" "$RUN"
  local lc_rc=$?
  set -e
  (( stage_rc > lc_rc )) && return "$stage_rc"
  return "$lc_rc"
}


# The batch builder: the stage probe's OWN transform (resize (128,256)
# BILINEAR, /255, ImageNet mean/std, CHW -- stage_probe.py _preprocess),
# inlined verbatim so the layer compare's batch is byte-for-byte what stage 1
# measured. Runs in-image (numpy, PIL), writes layercompare/batch.npy.
BATCH_PROG='import numpy as np
from PIL import Image
from pathlib import Path
SUFFIX = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
crops = sorted(x for x in Path("/work/crops").iterdir() if x.is_file() and x.suffix.lower() in SUFFIX)
if not crops:
    raise SystemExit("no crops found")
mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
def _pre(path):
    img = Image.open(path).convert("RGB").resize((128, 256), Image.Resampling.BILINEAR)
    arr = np.asarray(img, dtype=np.float32) / 255.0
    arr = (arr - mean) / std
    return np.ascontiguousarray(arr.transpose(2, 0, 1))
batch = np.stack([_pre(p) for p in crops]).astype(np.float32)
np.save("/work/layercompare/batch.npy", batch)
import json as _json
with open("/work/layercompare/batch.json", "w") as fh:
    _json.dump({"names": [p.name for p in crops],
                "rows": [r.reshape(-1).tolist() for r in batch]}, fh)
print(f"layercompare batch: {batch.shape} from {len(crops)} crops")'

# The layer compare: ONE program, two halves. The measure half (in-image,
# --measure) marks every intermediate tensor of the DECOMPOSED graph as a
# graph output, runs it under ORT CPU and under a diagnostic FP32 plan built
# from that same marked graph, and writes per-output per-crop cosine rows to
# run/layers.json. The report half (host, stdlib) prints the FIRST layer under
# the gate with its op type and name -- the box-1 deliverable -- or the clean
# reading; a missing/empty row set is the unknown-leg shape and exits 2.
write_layer_compare() {
  cat > "$RUN/layer_compare.py" <<'LAYERCMP'
"""[r312a] box 1: the layer-by-layer read of where the plan diverges.

Polygraphy is named in the box text but exists nowhere in the image or the
repo, and the probe container runs --network none, so the compare is built
from what the image already carries (onnx, onnxruntime, tensorrt): the SAME
mark-every-output rewrite Polygraphy would perform, applied to the DECOMPOSED
graph, run under ORT CPU and under a diagnostic FP32 plan built from that
same marked graph. Extra outputs do not change any layer's compute, so
per-layer divergence attribution stays valid.

The report half is stdlib-only and runs on the host (the CPU-only CI test
executes exactly this shipped half over fixture rows, like cosine_table.py).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

GATE = 0.999  # ruling 68, the same gate the stage table is judged by
run = Path(sys.argv[1])
LAYERS = run / "layers.json"


def report() -> int:
    """The box-1 deliverable: the FIRST layer under 0.999, with op type and name."""
    if not LAYERS.is_file():
        print("RESULT: INCONCLUSIVE - the layer measure never wrote layers.json")
        return 2
    rows = json.loads(LAYERS.read_text())
    if not rows:
        print("RESULT: INCONCLUSIVE - no marked layers were measured")
        return 2
    print(f"{'layer':6} {'name':44} {'op':14} {'min_cos':>9} {'mean_cos':>9}")
    first = None
    for r in rows:
        ok = float(r["min_cos"]) >= GATE
        print(f"{r['index']:<6} {str(r['name'])[:44]:44} {str(r['op_type'])[:14]:14} "
              f"{float(r['min_cos']):9.6f} {float(r['mean_cos']):9.6f}  "
              f"{'ok' if ok else 'FIRST DIVERGENCE'}")
        if not ok and first is None:
            first = r
    print()
    if first is None:
        print("RESULT: every measured layer reads at or above 0.999 - the plan divergence")
        print("does not enter at any marked layer on this batch")
    else:
        print(f"RESULT: the first layer under the gate is index {first['index']} "
              f"({first['op_type']}, {first['name']}) at min_cos {float(first['min_cos']):.6f}")
    return 0


def measure() -> None:
    """Mark every intermediate output of the decomposed graph, then measure
    ORT-CPU vs the diagnostic FP32 plan built from the same marked graph,
    per output per crop, and write rows to layers.json."""
    import numpy as np
    import onnx
    import onnxruntime as ort
    import torch
    from PIL import Image

    from ai.gateway.export.export_reid import MAX_BATCH, build_tensorrt_engine

    LC = run / "layercompare"
    # THE SAME batch, rebuilt from the run's own crops with the stage probe's
    # transform (resize (128,256) BILINEAR, /255, ImageNet mean/std, CHW) --
    # the box's "the same 36 crops", in the same sorted order the stage table's
    # crop-order guard depends on.
    SUFFIX = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    crops = sorted(x for x in (run / "crops").iterdir() if x.is_file() and x.suffix.lower() in SUFFIX)
    if not crops:
        raise SystemExit("no crops found")
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)

    def _pre(path):
        img = Image.open(path).convert("RGB").resize((128, 256), Image.Resampling.BILINEAR)
        arr = np.asarray(img, dtype=np.float32) / 255.0
        arr = (arr - mean) / std
        return np.ascontiguousarray(arr.transpose(2, 0, 1))

    batch = np.stack([_pre(p) for p in crops]).astype(np.float32)
    model = onnx.load(str(LC / "model.onnx"))  # the decomposed COPY, rc 0 verified

    # The marking: every tensor a node writes becomes a graph output too (the
    # original outputs are kept -- the final embedding stays first). The same
    # clear-output + re-add walk every marking tool performs.
    graph = model.graph
    final = [o.name for o in graph.output]
    seen = set(final)
    marked_names: list[str] = []
    meta: list[tuple[str, str]] = []  # (tensor name, producing op_type)
    for node in graph.node:
        for out in node.output:
            if out and out not in seen:
                seen.add(out)
                marked_names.append(out)
                meta.append((out, node.op_type))
    marked = onnx.ModelProto()
    marked.CopyFrom(model)
    # The type each marked output carries: ONNX requires graph outputs to be
    # FULLY typed ValueInfoProtos -- an output with a name and no type is
    # rejected by onnx.checker AND by the ORT/TensorRT loaders ("Field 'type'
    # of 'value_info' is required but missing"). The exporter already recorded
    # every intermediate tensor in graph.value_info (that is what the graph
    # viewer reads), so types are copied from there by NAME; a tensor the
    # exporter left out falls back to onnx.shape_inference on the decomposed
    # graph. A tensor neither source types is a real bug in the marking and
    # must fail loudly here, not silently ship a nameless-typed output.
    del marked.graph.output[:]
    type_by_name = {vi.name: vi for vi in graph.value_info}
    # The ORIGINAL outputs stay marked too (the final embedding must remain a
    # graph output): their types live in graph.output, which the marking walk
    # is about to clear -- harvest them FIRST. infer_shapes does not help
    # here: its inferred OUTPUTS land in the inferred graph.output, never in
    # value_info, so a final output absent from value_info is untyped unless
    # its original declaration is carried over.
    for vi in graph.output:
        type_by_name.setdefault(vi.name, vi)
    if len(type_by_name) < len(marked_names + final):
        inferred = onnx.shape_inference.infer_shapes(model)
        for vi in inferred.graph.value_info:
            type_by_name.setdefault(vi.name, vi)
    untyped = [
        name for name in marked_names + final
        if name not in type_by_name
    ]
    if untyped:
        raise SystemExit(
            f"{len(untyped)} marked outputs have no type in graph.value_info "
            f"nor from shape inference (first: {untyped[0]}) -- the marked "
            "graph would be rejected by onnx.checker/ORT/TRT"
        )
    for name in marked_names + final:
        marked.graph.output.add().CopyFrom(type_by_name[name])
    marked_path = LC / "marked.onnx"
    onnx.save(marked, str(marked_path))

    # ORT-CPU reference over the marked graph, chunked like the stage probe.
    sess = ort.InferenceSession(str(marked_path), providers=["CPUExecutionProvider"])
    in_name = sess.get_inputs()[0].name
    out_names = [o.name for o in sess.get_outputs()]
    ref: dict[str, list] = {}
    for i in range(0, len(batch), MAX_BATCH):
        chunk = batch[i : i + MAX_BATCH]
        got = sess.run(out_names, {in_name: np.ascontiguousarray(chunk, dtype=np.float32)})
        for nm, v in zip(out_names, got):
            ref.setdefault(nm, []).append(v)
    ref = {nm: np.concatenate(vs) for nm, vs in ref.items()}

    # The diagnostic FP32 plan from the SAME marked graph: no provenance gate
    # (build_tensorrt_engine, not compile_plan_from_validated_onnx) because
    # this plan is a diagnostic artifact under the run dir, never committed
    # or served.
    plan = LC / "marked-fp32.plan"
    build_tensorrt_engine(str(marked_path), str(plan), precision="fp32")

    # TRT leg, the repo's own binding idiom (torch CUDA tensors, addresses by
    # name, execute_async_v3 on the current stream) -- the same shape
    # stage_probe.py _trt_run uses.
    import tensorrt as trt

    logger = trt.Logger(trt.Logger.WARNING)
    with open(plan, "rb") as fh:  # nosemgrep: path-traversal-open
        engine = trt.Runtime(logger).deserialize_cuda_engine(fh.read())
    if engine is None:
        raise SystemExit(f"could not load {plan}")
    context = engine.create_execution_context()
    ins, outs = [], []
    for i in range(engine.num_io_tensors):
        nm = engine.get_tensor_name(i)
        (ins if engine.get_tensor_mode(nm) == trt.TensorIOMode.INPUT else outs).append(nm)
    if len(ins) != 1:
        raise SystemExit(f"expected 1 input tensor on the marked plan, got {ins}")
    got = set(outs)
    missing = [nm for nm in marked_names + final if nm not in got]
    if missing:
        raise SystemExit(
            f"{len(missing)} marked outputs are missing from the plan "
            f"(first: {missing[0]}) -- trtexec did not keep the extra outputs"
        )
    stream = torch.cuda.current_stream().cuda_stream
    trt_rows: dict[str, list] = {}
    for i in range(0, len(batch), MAX_BATCH):
        chunk = batch[i : i + MAX_BATCH]
        n = chunk.shape[0]
        context.set_input_shape(ins[0], chunk.shape)
        dev_in = torch.from_numpy(np.ascontiguousarray(chunk, dtype=np.float32)).cuda().contiguous()
        context.set_tensor_address(ins[0], dev_in.data_ptr())
        chunk_out = {}
        for nm in marked_names + final:
            shape = tuple(context.get_tensor_shape(nm))
            dev = torch.empty(int(np.prod(shape)) if shape else 1, dtype=torch.float32, device="cuda")
            context.set_tensor_address(nm, dev.data_ptr())
            chunk_out[nm] = (dev, shape)
        if not context.execute_async_v3(stream):
            raise SystemExit(f"execute_async_v3 failed on the marked plan at row {i}")
        torch.cuda.synchronize()
        for nm, (dev, shape) in chunk_out.items():
            trt_rows.setdefault(nm, []).append(dev.cpu().numpy().reshape((n,) + shape[1:]))
    trt_out = {nm: np.concatenate(vs) for nm, vs in trt_rows.items()}

    # Per-output per-crop cosine rows. An output whose ORT view is a scalar
    # (or otherwise not rank-2) is reshaped per crop for the comparison.
    rows = []
    for idx, (nm, op) in enumerate(meta):
        a, b = ref[nm], trt_out[nm]
        a2 = a.reshape((len(batch), -1)) if a.ndim > 1 and a.shape[0] == len(batch) else a.reshape((len(batch), -1))
        b2 = b.reshape((len(batch), -1))
        na = np.linalg.norm(a2, axis=1)
        nb = np.linalg.norm(b2, axis=1)
        dot = (a2 * b2).sum(axis=1)
        cos = np.divide(dot, na * nb, out=np.zeros_like(dot), where=(na > 0) & (nb > 0))
        rows.append(
            {
                "index": idx,
                "name": nm,
                "op_type": op,
                "min_cos": float(cos.min()),
                "mean_cos": float(cos.mean()),
            }
        )
    LAYERS.write_text(json.dumps(rows))
    print(f"layer measure: {len(rows)} marked layers x {len(batch)} crops -> layers.json")


if __name__ == "__main__":
    if "--measure" in sys.argv[2:]:
        measure()
    else:
        sys.exit(report())
LAYERCMP
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
  layercompare)
    run_layercompare
    ;;
esac

nvidia-smi --query-gpu=index,memory.used,memory.total --format=csv > "$RUN/gpu-after-test.txt"
exit "${rc:-0}"
