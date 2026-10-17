#!/usr/bin/env bash
# [r195] box-2 probe: on THIS host, can a container reach a port the host publishes on its OWN
# LOOPBACK, and at what address?
#
# Why measure rather than reason. agent-gpu publishes the VLM port on the host loopback: the owner's
# maui run read http://127.0.0.1:18100/health -> {"status":"ok"} while host.docker.internal had no
# DNS entry on that host (witness 6193951294). [r195] made the HARNESS dial that loopback form, but
# the run's backend container still gets the alias as AI_VLM_URL -- a container is not a host login.
# The package's second clause asks how the CONTAINER reaches the port, "by a route the PR measures
# and names". A rootless engine gives the container its own network namespace, so the host's
# 127.0.0.1 is not the container's. Which of the built-in aliases, or the slirp gateway address, or
# nothing at all reaches a LOOPBACK-ONLY host listener depends on the engine, its version, whether
# it is rootless, and which rootless network stack is in use (pasta or slirp4netns). Four plausible
# answers; only this host can say which. Naming a guessed one is what the clause forbids.
#
# Two-sided so a missing tool cannot read as "no route": the listener is started twice -- once on
# 0.0.0.0 and once on 127.0.0.1 -- with every other input held fixed. A target that is open on
# 0.0.0.0 and closed on 127.0.0.1 is the real finding (the alias exists; host loopback is not
# forwarded). A target closed in BOTH is "this client cannot measure", not "no route", and the
# probe says which it saw.
#
# It is a probe, not a real-tier run: one `--rm` container per test, no compose project, no volumes,
# nothing under any run root, no GPU container, and it needs neither agent-gpu nor the GPU. It binds
# its OWN free test port and refuses to start if that port is taken, so it cannot disturb a live
# stack (UR-133). Tear-down is the listener it started, and nothing else (UR-135).
#
# Exit: 0 measured (whatever the answer was), 2 could not measure (prerequisite missing).
set -uo pipefail

PORT="${R195_PROBE_PORT:-18123}"
IMG="${R195_PROBE_IMAGE:-}"
LISTENER=""

note() { printf '\n== %s\n' "$*"; }
obs()  { printf 'OBSERVED %s\n' "$*"; }

# ss -ltnH prints "LISTEN 0 5 0.0.0.0:18123 0.0.0.0:*" -- the local address is column 4 and the
# port is NOT at end of line, so any "port at end of line" pattern matches nothing. Read column 4.
listen_line() { ss -ltnH 2>/dev/null | awk '{print $4}' | grep -E "[:.]${PORT}\$" | head -1; }
listen_seen() { [[ -n "$(listen_line)" ]]; }

cleanup() { [[ -n "$LISTENER" ]] && kill "$LISTENER" 2>/dev/null; return 0; }
trap cleanup EXIT INT TERM

[[ "$PORT" =~ ^[0-9]+$ ]] || { obs "R195_PROBE_PORT must be a number, got: $PORT"; exit 2; }

# --- engine ---------------------------------------------------------------------
# The harness reaches maui's engine with the moby CLI over podman's Docker-compatible socket
# (DOCKER_HOST=unix://$PODMAN_SOCKET; deliberately not `--engine podman`, because podman-compose
# cannot express the override's !override/!reset tags). So the route must hold for the client the
# run uses: that client is what the default case below tests. podman is used only to force a
# specific rootless network stack, which the moby CLI cannot name.
CLI=""
for c in docker podman; do
  command -v "$c" >/dev/null 2>&1 && { CLI="$c"; break; }
done
[[ -z "$CLI" ]] && { obs "neither docker nor podman on PATH -- nothing to measure"; exit 2; }
PODMAN=""
command -v podman >/dev/null 2>&1 && PODMAN=podman

note "engine"
obs "client=$CLI server=$("$CLI" version --format '{{.Server.Version}}' 2>&1 | head -1)"
obs "DOCKER_HOST=${DOCKER_HOST:-<unset>}  uid=$(id -u)  XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-<unset>}"
[[ -n "$PODMAN" ]] && obs "podman rootless=$(podman info --format '{{.Host.Security.Rootless}}' 2>/dev/null)"

# --- image carrying a TCP client -------------------------------------------------
note "image and client"
if [[ -z "$IMG" ]]; then
  while IFS= read -r cand; do
    [[ -z "$cand" ]] && continue
    [[ "$cand" == *"<none>"* ]] && continue
    IMG="$cand"; break
  done < <("$CLI" images --format '{{.Repository}}:{{.Tag}}' 2>/dev/null)
fi
[[ -z "$IMG" ]] && { obs "no local image to run a client from -- set R195_PROBE_IMAGE=<image:tag>"; exit 2; }
obs "image=$IMG (used as already present on this host; no pull)"

# A TCP connect is the whole measurement -- does that address:port answer. HTTP would add a second
# variable (which client the image carries, whether the server answers), so it is not used. Three
# client forms are tried in order and the one actually used is printed, so "closed" always means
# "a client tried and got no answer" and never "no client existed".
CLIENT_PROBE='
c=$1; pt=$2
if command -v python3 >/dev/null 2>&1; then used=python3
elif command -v nc >/dev/null 2>&1; then used=nc
elif command -v bash >/dev/null 2>&1; then used=bash
else echo "no-client"; exit 0; fi
case $used in
python3) r=$(python3 -c "import socket,sys
s=socket.socket(); s.settimeout(4)
try:
    s.connect((sys.argv[1],int(sys.argv[2]))); print(\"open\")
except Exception:
    print(\"closed\")" "$c" "$pt") ;;
nc)   if nc -z -w4 "$c" "$pt" 2>/dev/null; then r=open; else r=closed; fi ;;
bash) if bash -c "exec 3<>/dev/tcp/$c/$pt" 2>/dev/null; then r=open; else r=closed; fi ;;
esac
echo "$used $r"'

reach() { # $1 = CLI, $2 = extra run args, $3 = address -> prints "<client> <verdict>"
  local cli="$1" pre="$2" addr="$3" out
  # $pre comes only from the fixed list in start_and_sweep and $addr only from TARGETS, never from
  # anything the host supplies, so the word-split expansion below carries nothing untrusted.
  out=$($cli run --rm $pre "$IMG" sh -c "$CLIENT_PROBE" sh "$addr" "$PORT" 2>&1)
  # A row whose container never started carries an engine error. Drop podman's timestamp/level/msg
  # wrapper and its random container id -- neither is a measurement -- and keep the TAIL, because the
  # reason follows "failed:". A head cut would keep the id and discard the reason.
  out=$(printf '%s' "$out" | tr '\n' '|' | sed -E 's/time=[^ ]+ level=[a-z]+ msg=//g; s/Preparing container [0-9a-f]+: //g' | tail -c 200)
  printf '%s' "${out:-<empty-output>}"
}

TARGETS="host.docker.internal host.containers.internal gateway.docker.internal 10.0.2.2 127.0.0.1"

sweep() { # $1 heading, $2 CLI, $3 prefix args
  note "$1"
  local cli="$2" pre="$3" t r
  for t in $TARGETS; do
    r=$(reach "$cli" "$pre" "$t")
    printf '  %-26s %s\n' "$t" "$r"
  done
}

# --- what the container can name at all -------------------------------------------
note "resolution inside a container (the names it can even look up)"
"$CLI" run --rm "$IMG" sh -c 'echo "--- /etc/hosts"; cat /etc/hosts; echo "--- lookups"; for n in host.containers.internal host.docker.internal gateway.docker.internal; do printf "%-26s %s\n" "$n" "$(getent hosts $n | awk "{print \$1}" | head -1)"; done' 2>&1 | sed 's/^/  /'

# --- the listener, twice ---------------------------------------------------------
note "listener"
if ! command -v python3 >/dev/null 2>&1; then
  obs "python3 missing on the host: the probe cannot raise its own listener, so it cannot create"
  obs "the loopback-only condition it measures. Refusing to conclude from a listener it did not"
  obs "start. Install python3 (any build) or run this where one exists."
  exit 2
fi
if listen_seen; then
  obs "port $PORT is already in use -- refusing to disturb it. Re-run with R195_PROBE_PORT=<free port>"
  exit 2
fi

start_and_sweep() { # $1 bind address, $2 heading
  python3 -m http.server "$PORT" --bind "$1" >/dev/null 2>&1 &
  LISTENER=$!
  sleep 1.5
  # The port is one column, not the end of the line: `ss -ltnH` prints
  # "LISTEN 0 5 0.0.0.0:18123 0.0.0.0:*", so a pattern anchored to $ matches nothing and would
  # make a healthy listener read as "never came up". Take the local-address column (4).
  if ! listen_seen; then
    obs "listener on $1:$PORT never came up -- cannot conclude"
    return 1
  fi
  obs "listener as seen by the host: $(listen_line | tr -s ' ')"
  sweep "$2 -- the run's own client, default network" "$CLI" ""
  sweep "$2 -- the run's client, --network host (control: shares host loopback)" "$CLI" "--network host"
  if [[ -n "$PODMAN" ]]; then
    sweep "$2 -- podman, slirp4netns with allow_host_loopback=true" podman "--network slirp4netns:allow_host_loopback=true"
    sweep "$2 -- podman, pasta" podman "--network pasta"
  fi
  kill "$LISTENER" 2>/dev/null; LISTENER=""; sleep 0.5
  return 0
}

start_and_sweep 0.0.0.0 "CONTROL listener on 0.0.0.0 (every interface)" || exit 2
start_and_sweep 127.0.0.1 "UNDER TEST listener on 127.0.0.1 ONLY (what agent-gpu publishes)" || exit 2

note "how to read it"
obs "A target open under the 0.0.0.0 control and closed under 127.0.0.1, in the same row, is the"
obs "finding: that alias resolves and routes, but this rootless stack does not forward the host's"
obs "loopback to the container. Closed in both rows is not a route -- it means that client could"
obs "not be used here, and says nothing about the route. --network host open on 127.0.0.1 proves"
obs "the listener and the client work, so a closed alias row is a routing fact, not a broken probe."
obs "Choosing between the owner options (agent-gpu publishing beyond loopback, vs the container"
obs "sharing the host namespace) is not this probe's call."
exit 0
