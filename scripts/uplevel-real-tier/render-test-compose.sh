#!/usr/bin/env bash
# Render + refuse: the gate between "I read operator.md" and "something started".
#
# Implements docs/uplevel/operator.md step 4 ("Render the configuration first and refuse to
# start when any value points at host.docker.internal …") and the owner-vet list from
# "The owner on the host" steps 1-2 (-p project, own env file, non-default ports, fresh
# camera dir, no live mounts, no Podman socket, ORCHESTRATOR_ENABLED=false) — mechanically,
# against the `docker compose config` render of the prod file PLUS
# scripts/uplevel-real-tier/docker-compose.b14-real.yml. It starts NOTHING.
#
# Usage (from a checkout root):
#   scripts/uplevel-real-tier/render-test-compose.sh --project b14-run7 \
#       --runner-url http://host.docker.internal:18123
#   scripts/uplevel-real-tier/render-test-compose.sh --project b14-demo --demo
#
# --runner-url is the port line `agent-gpu run` printed (operator.md step 3); required unless
# --demo. --demo rehearses against vlm-mock.mjs (no GPU, not evidence — see README).
# Exit: 0 = render passed every gate (commands printed); 1 = a gate refused (nothing to run).

set -euo pipefail

die() { printf 'REFUSED: %s\n' "$1" >&2; exit 1; }
warn() { printf 'warning: %s\n' "$1" >&2; }

PROJECT="" RUNNER_URL="" DEMO=0 BACKEND_IMAGE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --project) PROJECT="${2:-}"; shift 2 ;;
    --runner-url) RUNNER_URL="${2:-}"; shift 2 ;;
    --backend-image) BACKEND_IMAGE="${2:-}"; shift 2 ;;
    --demo) DEMO=1; shift ;;
    -h|--help) sed -n '2,21p' "$0"; exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
done

command -v docker >/dev/null || die "docker not on PATH"
command -v jq >/dev/null || die "jq not on PATH"
docker compose version >/dev/null 2>&1 || die "docker compose not available"
printf '%s\n' "$PROJECT" | grep -Eq '^[a-z0-9][a-z0-9-]{0,40}$' \
  || die "--project must match ^[a-z0-9][a-z0-9-]{0,40}$ (compose-safe, never empty)"
[ -f docker-compose.prod.yml ] || die "run from a checkout root (docker-compose.prod.yml not found)"
[ -f scripts/uplevel-real-tier/docker-compose.b14-real.yml ] \
  || die "run from a checkout root (the override file is not here)"
RUNNER_PORT=""
if [ "$DEMO" -eq 0 ]; then
  [ -n "$RUNNER_URL" ] || die "--runner-url (the port line agent-gpu run printed) is required without --demo"
  printf '%s\n' "$RUNNER_URL" | grep -Eq '^http://host\.docker\.internal:[0-9]{2,5}$' \
    || die "--runner-url must be exactly http://host.docker.internal:<port> (operator.md step 3)"
  RUNNER_PORT="${RUNNER_URL##*:}"
  if [ "$RUNNER_PORT" -lt 18100 ] || [ "$RUNNER_PORT" -gt 18199 ]; then
    warn "runner port $RUNNER_PORT is outside the 18100-18199 pool operator.md documents — re-read the agent-gpu run output"
  fi
fi

# Live-stack loopback ports (live API/db/engines/web). A test render publishes NOTHING here:
# a curl to these numbers must answer only from the live stack, or from nobody.
LIVE_PORTS=" 8000 5432 6379 8098 8090 1984 8554 8555 3000 8080 "
API_PORT="${B14_API_PORT:-18000}"; PG_PORT="${B14_PG_PORT:-18001}"
REDIS_PORT="${B14_REDIS_PORT:-18002}"; PROXY_PORT="${B14_PROXY_PORT:-18003}"
for p in "$API_PORT" "$PG_PORT" "$REDIS_PORT" "$PROXY_PORT"; do
  case "$LIVE_PORTS" in *" $p "*) die "run port $p is a live-stack port — set B14_*_PORT overrides" ;; esac
done

RUN_DIR="b14run/$PROJECT"
ENV_FILE="$RUN_DIR/.env.b14"
[ -e "$ENV_FILE" ] && warn "$ENV_FILE already exists — reusing it (password stays put; rm -rf the dir for a fresh run)"

mkdir -p "$RUN_DIR/data" "$RUN_DIR/cam" "$RUN_DIR/models" "$RUN_DIR/hf" "$RUN_DIR/state"
printf '# runtime dir of one B1.4 test run: env file (holds a password), renders, logs\n*\n' > "$RUN_DIR/.gitignore"
: > "$RUN_DIR/dummy.sock"   # PODMAN_SOCKET placeholder — never the host's real socket
ABS_RUN="$(cd "$RUN_DIR" && pwd)"
if [ ! -e "$ENV_FILE" ]; then
  PASS="$(head -c 48 /dev/urandom | tr -dc 'A-Za-z0-9')"
  [ -n "$PASS" ] || die "could not generate a postgres password"
  {
    echo "# run env for the B1.4 real-tier test deployment — generated $(date -u +%FT%TZ) by render-test-compose.sh"
    echo "# never the checkout's .env; never shared between runs"
    echo "POSTGRES_PASSWORD=${PASS}"
    echo "PODMAN_SOCKET=${ABS_RUN}/dummy.sock"
    echo "API_PORT=${API_PORT}"
    echo "POSTGRES_PORT=${PG_PORT}"
    echo "REDIS_PORT=${REDIS_PORT}"
    echo "B14_PROXY_PORT=${PROXY_PORT}"
    echo "LOG_LEVEL=INFO"   # B1.4's transition line is INFO-only (verdict_engine_status.py:216-217)
    echo "B14_UID=$(id -u)"
    echo "B14_GID=$(id -g)"
    echo "B14_DATA_DIR=${ABS_RUN}/data"
    echo "B14_CAM_DIR=${ABS_RUN}/cam"
    echo "B14_MODELS_DIR=${ABS_RUN}/models"
    echo "B14_HF_DIR=${ABS_RUN}/hf"
    echo "B14_DUMMY_SOCKET=${ABS_RUN}/dummy.sock"
    echo "B14_STATE_DIR=${ABS_RUN}/state"
    if [ "$DEMO" -eq 1 ]; then echo "VLMPROXY_TARGET=vlm-mock:8098"; else echo "VLMPROXY_TARGET=${RUNNER_URL}"; fi
    [ -n "$BACKEND_IMAGE" ] && echo "B14_BACKEND_IMAGE=${BACKEND_IMAGE}"
    true
  } > "$ENV_FILE"
  chmod 600 "$ENV_FILE"
fi

COMPOSE=(docker compose -p "$PROJECT" -f docker-compose.prod.yml
         -f scripts/uplevel-real-tier/docker-compose.b14-real.yml --env-file "$ENV_FILE")
[ "$DEMO" -eq 1 ] && COMPOSE+=(--profile mock)

"${COMPOSE[@]}" config --format json > "$RUN_DIR/rendered.json" 2>"$RUN_DIR/render.err" \
  || die "compose config failed to render (see $RUN_DIR/render.err)"
"${COMPOSE[@]}" config > "$RUN_DIR/rendered.yml" 2>/dev/null || true
J="$RUN_DIR/rendered.json"

# gate 1 — exactly the services this run may have (GPU fleet + live infra are profile-excluded)
SELECTED="$("${COMPOSE[@]}" config --services | LC_ALL=C sort | tr '\n' ' ')"
EXPECTED="backend postgres redis vlm-proxy "
[ "$DEMO" -eq 1 ] && EXPECTED="backend postgres redis vlm-mock vlm-proxy "
[ "$SELECTED" = "$EXPECTED" ] \
  || die "selection is [$SELECTED], expected [$EXPECTED] — an excluded service leaked into the run"

# gate 2 — every published port loopback-only, none on a live-stack port (jq returns the
# published port as a STRING; compare as strings)
BAD="$(jq -r '
  [ .services[] | .ports // [] | .[]
    | select((.host_ip // "") != "127.0.0.1") | "non-loopback publish \(.host_ip // "0.0.0.0"):\(.published)" ]
  + [ .services[] | .ports // [] | .[]
    | . as $e | select(((["8000","5432","6379","8098","8090","1984","8554","8555","3000","8080"]
        | index($e.published))) != null)
    | "live-stack port \($e.published)" ] | .[]' "$J")"
[ -z "$BAD" ] || die "port guards: $BAD"

# gate 3 — host.docker.internal (the one way out, operator.md) appears ONLY as the proxy's
# target (real runs) or nowhere at all (demo)
HDI_ALL="$(jq -r '[.. | strings | select(test("host[.]docker[.]internal"))] | length' "$J")"
if [ "$DEMO" -eq 1 ]; then
  [ "$HDI_ALL" = "0" ] || die "demo render mentions host.docker.internal $HDI_ALL time(s) — a mock run must not reach the host at all"
else
  TARGET="$(jq -r '.services["vlm-proxy"].environment.VLMPROXY_TARGET // ""' "$J")"
  [ "$TARGET" = "$RUNNER_URL" ] || die "vlm-proxy target is [$TARGET], expected [$RUNNER_URL]"
  [ "$HDI_ALL" = "1" ] || die "host.docker.internal appears $HDI_ALL time(s), expected exactly 1 (the proxy's target) — nothing else may point at the host (operator.md step 4)"
fi

# gate 4 — the backend's mounts are exactly the run's fresh dirs + the dummy socket (+ the
# prod file read-only); no live path, no host socket, no :U re-own anywhere
SRC_SET="$(jq -r '.services.backend.volumes // [] | .[].source' "$J" | LC_ALL=C sort | tr '\n' ' ')"
EXPECTED_SRCS="$(printf '%s\n' "$ABS_RUN/cam" "$ABS_RUN/data" "$ABS_RUN/dummy.sock" \
  "$ABS_RUN/hf" "$ABS_RUN/models" "$(pwd)/docker-compose.prod.yml" | LC_ALL=C sort | tr '\n' ' ')"
[ "$SRC_SET" = "$EXPECTED_SRCS" ] \
  || die "backend mount sources are [$SRC_SET], expected exactly [$EXPECTED_SRCS] (a live path or socket survived the merge)"
U_FLAGS="$(jq -r '[.. | objects | select(has("bind")) | .bind // {}
               | select((.selinux // "") | test("U"))] | length' "$J")"
[ "$U_FLAGS" = "0" ] || die "a bind mount carries :U (recursive re-own — operator.md names ./backend/data:z,U at prod :459)"

# gate 5 — the live-stack interference switches are off (and the indirection is wired)
EN="$(jq -r '.services.backend.environment.ORCHESTRATOR_ENABLED // "absent"' "$J")"
[ "$EN" = "false" ] || die "ORCHESTRATOR_ENABLED=[$EN] — must be false: the orchestrator restarts containers by NAME in every project"
AIURL="$(jq -r '.services.backend.environment.AI_VLM_URL // "absent"' "$J")"
[ "$AIURL" = "http://vlm-proxy:8098" ] || die "backend AI_VLM_URL=[$AIURL] — ruling 22's fixed indirection is not wired"
LOGLEV="$(jq -r '.services.backend.environment.LOG_LEVEL // "absent"' "$J")"
[ "$LOGLEV" = "INFO" ] || die "backend LOG_LEVEL=[$LOGLEV] — the tracker's transition line (the grep'd evidence) is INFO-only and would be invisible"
WOGATE="$(jq -r '.services.backend.environment.READINESS_REQUIRE_PIPELINE_WORKERS // "absent"' "$J")"
[ "$WOGATE" = "false" ] || warn "READINESS_REQUIRE_PIPELINE_WORKERS=[$WOGATE] (prod's own default is false, docker-compose.prod.yml:638): with it non-false, ready can 503 on workers rather than the engine — re-read README step C before reading a flip"

# gate 6 — don't stack onto containers already under this project name
if [ -n "$("${COMPOSE[@]}" ps -q 2>/dev/null)" ]; then
  die "project $PROJECT already has containers — tear the old run down first (README step D), or pick a new --project"
fi

# port sanity (a warning, not a refusal — ss sees the HOST's listeners; on the operator's
# sandbox Docker that IS where these get published)
if command -v ss >/dev/null 2>&1; then
  for p in "$API_PORT" "$PG_PORT" "$REDIS_PORT" "$PROXY_PORT"; do
    if ss -ltn 2>/dev/null | grep -Eq "[:.]${p}[[:space:]]"; then
      warn "something already listens on ${p} — set a different B14_*_PORT and re-render"
    fi
  done
fi

IMG="${BACKEND_IMAGE:-$(jq -r '.services.backend.image' "$J")}"
docker image inspect "$IMG" >/dev/null 2>&1 \
  || warn "image [$IMG] not present locally — docker pull it (or build+tag) before up: the override resets build:, so up will NOT build it"

echo "PASS — every gate held. Full render: $RUN_DIR/rendered.yml (machine: $RUN_DIR/rendered.json)"
echo
echo "Bring up:"
echo "  ${COMPOSE[*]} up -d"
echo "Then readiness (expect ready=true, status=ready, verdict_engine.state=available):"
echo "  curl -s localhost:${API_PORT}/api/system/health/ready | jq '{ready, status, verdict_engine}'"
echo "Then the check + teardown: scripts/uplevel-real-tier/README.md steps C and D (project: ${PROJECT})."
