#!/usr/bin/env bash
# O2.5 Step 1 spike probe (ruling 144): can `docker-compose.prod.yml` come up as a
# disposable test deployment under ROOTLESS Podman inside an uplevel sandbox?
#
# It prints OBSERVED for each claim the spike's answer rests on, in the order the
# answer needs them: the four sandbox mechanisms that decide rootless storage and
# limits; the differential control that isolates resource limits as the blocker (same
# image, entrypoint overridden, limits on vs off); then the bring-up of the two image
# services the committed minimal override covers, checked against each one.
#
# This is a TEST DEPLOYMENT (UR-133): its own compose project, its own generated env
# file (never the checkout's .env), remapped ports, its own volumes, its own camera
# directory. It starts no GPU container and touches no live stack. It tears down with
# `<compose> -p <project> down -v` and nothing else (UR-135), also on failure.
#
# Exit: 0 both services answered; 2 a prerequisite is missing; 3 the bring-up failed.
set -uo pipefail

REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
COMPOSE="$REPO/docker-compose.prod.yml"
OVERRIDE="$REPO/scripts/uplevel/prod-shape-override.yml"
RUNDIR=$(mktemp -d /tmp/o25-probe.XXXXXX)
PROJECT=hsi-probe-$$
ENVF="$RUNDIR/env"
SOCK="${XDG_RUNTIME_DIR:?}/podman/podman.sock"
STORAGE=/home/agent/.local/share/containers/storage

# The storage driver is set in storage.conf (CONTAINERS_STORAGE_CONF), not containers.conf.
# It must be set in config rather than by the `--storage-driver` flag, because the flag is
# refused on an existing database: "database graph driver overlay does not match vfs".
printf '[storage]\ndriver = "vfs"\n' > "$RUNDIR/storage.conf"
export CONTAINERS_STORAGE_CONF="$RUNDIR/storage.conf"
export DOCKER_HOST="unix://$SOCK" XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:?}"

note() { printf '\n== %s\n' "$*"; }
obs()  { printf 'OBSERVED %s\n' "$*"; }
cleanup() { [[ -n ${DUP:-} ]] && "${DC[@]}" -p "$PROJECT" -f "$COMPOSE" -f "$OVERRIDE" --env-file "$ENVF" down -v >/dev/null 2>&1; rm -rf "$RUNDIR"; }
trap cleanup EXIT INT TERM

command -v podman >/dev/null || { obs "podman not installed"; exit 2; }

# --- UR-133/134: the run's own env file, ports, camera dir ---------------------------
POSTGRES_PASSWORD=$(head -c 12 /dev/urandom | od -An -tx1 | tr -d ' \n')
cat > "$ENVF" <<EOF
POSTGRES_PASSWORD=$POSTGRES_PASSWORD
PODMAN_SOCKET=$SOCK
FOSCAM_BASE_PATH=$RUNDIR/cam
TZ=UTC
EOF
mkdir -p "$RUNDIR/cam"
export POSTGRES_PASSWORD PODMAN_SOCKET="$SOCK" FOSCAM_BASE_PATH="$RUNDIR/cam"
obs "env file $ENVF (generated password; never the checkout's .env)"
obs "project=$PROJECT camera dir=$RUNDIR/cam host ports 15432/16379"

# --- the mechanisms that decide whether rootless storage works here ------------------
note "sandbox mechanisms"
obs "sudo uid: $(sudo -n id -u 2>&1 | head -1) (UR-176 allows sudo for development installs only)"
mkdir -p "$RUNDIR/ovl"/{u,w,m}
sudo -n mount -t overlay overlay -o "lowerdir=/usr,upperdir=$RUNDIR/ovl/u,workdir=$RUNDIR/ovl/w" "$RUNDIR/ovl/m" >/dev/null 2>&1
obs "root 'mount -t overlay': rc=$? (nonzero = overlayfs cannot be mounted here at all)"
python3 -c 'import os,sys
try: os.close(os.open("/dev/fuse", os.O_RDWR))
except OSError as e: print("OBSERVED opening /dev/fuse:", e.strerror); sys.exit(1)
print("OBSERVED opening /dev/fuse: ok")'
CG=$(awk -F: '$1=="0"{print $3}' /proc/self/cgroup)
obs "cgroup $CG: controllers=[$(cat /sys/fs/cgroup$CG/cgroup.controllers 2>&1)] delegated=[$(cat /sys/fs/cgroup$CG/cgroup.subtree_control 2>&1)]"
mkdir "/sys/fs/cgroup$CG/o25-probe" 2>&1 | head -1 | sed 's/^/OBSERVED mkdir under own cgroup: /'
rmdir "/sys/fs/cgroup$CG/o25-probe" 2>/dev/null

# --- the differential control: is it the image, or the limits? -----------------------
note "differential control (same image, limits on vs off)"
pgrep -f "system service --time=0 unix://$SOCK" >/dev/null || {
  mkdir -p "$(dirname "$SOCK")"
  nohup podman system service --time=0 "unix://$SOCK" >"$RUNDIR/svc.log" 2>&1 &
  until [ -S "$SOCK" ]; do sleep 1; done
}
obs "storage driver in use: $(podman info --format '{{.Store.GraphDriverName}}' 2>&1 | tail -1)"
IMG=public.ecr.aws/docker/library/redis:7.4-alpine3.21
podman pull -q "$IMG" >"$RUNDIR/pull.log" 2>&1 || obs "pull failed: $(tail -1 "$RUNDIR/pull.log")"
start_one() { # $1 = limit flag, $2 = label. --entrypoint overrides the image's own
  podman rm -f o25-ctl >/dev/null 2>&1
  local out rc st
  out=$(podman run -d --name o25-ctl ${1:+$1} --entrypoint /bin/sh "$IMG" -c 'sleep 20' 2>&1); rc=$?
  st=$(podman ps --format '{{.Status}}' -f name=o25-ctl 2>/dev/null)
  obs "$2 rc=$rc status='${st:-none}' $(echo "$out" | grep -m1 -oE 'rootless needs no limits[^\"]*' | sed 's/^/msg=/')"
  podman rm -f o25-ctl >/dev/null 2>&1
}
start_one ""              "no limits     :"
start_one "--memory=512m" "with --memory :"
start_one "--cpus=1"      "with --cpus=1 :"

DC=(docker compose)
command -v docker >/dev/null || DC=(podman-compose)
obs "compose CLI: ${DC[*]}"

# --- the negative control: limits kept, ports remapped -------------------------------
# The spike's headline claim is that the file's resource limits block a rootless bring-up,
# so a reviewer can watch exactly that fail. The control keeps the prod file's
# `deploy.resources.limits` and remaps ONLY its ports: publishing the production ports
# (5432/6379) from a test deployment would be both a UR-133 violation and a collision
# hazard on a host that runs the live stack, and it would confound the answer with a
# port error. This is the ports half of prod-shape-override.yml without the deploy reset.
note "negative control: prod file with ports remapped but limits KEPT"
cat > "$RUNDIR/ports-only.yml" <<'EOF'
services:
  postgres:
    ports: !override
      - "15432:5432"
  redis:
    ports: !override
      - "16379:6379"
EOF
CTL="$PROJECT-ctl"
CTLARGS=(-p "$CTL" -f "$COMPOSE" -f "$RUNDIR/ports-only.yml" --env-file "$ENVF")
if "${DC[@]}" "${CTLARGS[@]}" up -d postgres redis >"$RUNDIR/ctl.log" 2>&1; then
  obs "limits kept: came up -- the limits are NOT the blocker"
else
  obs "limits kept: FAILED -> $(grep -m1 -oE 'rootless needs no limits[^\"]*|Error response from daemon: [^\"]*' "$RUNDIR/ctl.log" | cut -c1-150)"
fi
"${DC[@]}" "${CTLARGS[@]}" down -v >/dev/null 2>&1

# --- the bring-up the override makes possible ----------------------------------------
note "bring-up: docker-compose.prod.yml + prod-shape-override.yml, rootless"
DUP=1
# pipefail is on, so the pipeline's status is compose's, not tail's.
if ! "${DC[@]}" -p "$PROJECT" -f "$COMPOSE" -f "$OVERRIDE" --env-file "$ENVF" up -d postgres redis >"$RUNDIR/up.log" 2>&1; then
  obs "bring-up FAILED: $(grep -m1 -iE 'error|denied|no space' "$RUNDIR/up.log" | cut -c1-160)"
  tail -3 "$RUNDIR/up.log"
  exit 3
fi
tail -3 "$RUNDIR/up.log"
"${DC[@]}" -p "$PROJECT" -f "$COMPOSE" -f "$OVERRIDE" --env-file "$ENVF" ps 2>/dev/null | tail -3
obs "redis PING: $(podman exec "${PROJECT}-redis-1" redis-cli ping 2>&1 || true)"
# postgres needs a few seconds of initdb before it answers; wait, then ask.
PGREADY=$(for _ in $(seq 1 20); do
  o=$(podman exec "${PROJECT}-postgres-1" pg_isready -q 2>&1) && break; sleep 1
done; echo "${o:-accepting connections}")
obs "postgres pg_isready: $PGREADY"
for p in 15432 16379; do
  timeout 5 bash -c "exec 3<>/dev/tcp/127.0.0.1/$p" 2>/dev/null && obs "host port $p: TCP ok" || obs "host port $p: refused"
done
obs "containers storage after the run: $(du -sh "$STORAGE" 2>/dev/null | cut -f1)"
note "teardown (UR-135: down -v only)"
"${DC[@]}" -p "$PROJECT" -f "$COMPOSE" -f "$OVERRIDE" --env-file "$ENVF" down -v 2>&1 | tail -3
DUP=
exit 0
