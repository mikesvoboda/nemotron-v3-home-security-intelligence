#!/usr/bin/env bash
# [r195] box-2 probe v2: on THIS host, can a container reach a port the host publishes on its OWN
# LOOPBACK, and at what address?
#
# Why measure rather than reason. agent-gpu publishes the VLM port on the host loopback: the owner's
# maui run read http://127.0.0.1:18100/health -> {"status":"ok"} while host.docker.internal had no
# DNS entry on that host (witness 6193951294). [r195] made the HARNESS dial that loopback form, but
# the run's backend container still gets the alias as AI_VLM_URL -- a container is not a host login.
# The package's second clause asks how the CONTAINER reaches the port, "by a route the PR measures
# and names". A rootless engine gives the container its own network namespace, so the host's
# 127.0.0.1 is not the container's. Which of the built-in aliases, a bridge gateway, or nothing at
# all reaches a LOOPBACK-ONLY host listener depends on the engine, whether it is rootless, which
# network stack is in use (bridge, pasta, slirp4netns, host) and whether the run adds a host alias
# at all. Several plausible answers; only this host can say which. Naming a guessed one is what the
# clause forbids.
#
# WHAT v2 CHANGES, and why -- all three learned from the owner's v1 run at 1aa146a49 (his relay on
# this PR, 2026-10-17T14:0xZ, which measured nothing about the route it was asked about):
#   1. ENGINE. v1 picked the first CLI on PATH, so it measured the docker CE daemon on the docker0
#      bridge. That is NOT the client the harness uses: it reaches maui's rootless Podman through
#      podman's Docker-compatible socket (scripts/setup-container-api.sh:55-58, and this project
#      deliberately uses the moby CLI rather than `--engine podman` because podman-compose cannot
#      express the override's !override/!reset tags). v1's run reported DOCKER_HOST=<unset> at the
#      login, so "docker is on PATH" proved nothing about which engine the run gets. v2 measures the
#      harness route EXPLICITLY by setting DOCKER_HOST to the socket, and says which leg it ran.
#   2. IMAGE. v1 took the first image from `$CLI images` -- docker's store -- and handed it to
#      podman, whose store does not have it. All 20 podman rows then died in name resolution before
#      a single connect, measuring nothing. v2 resolves an image PER CLIENT from that client's own
#      store and refuses a leg whose image that client cannot see, labelled NOT-MEASURED.
#   3. TARGETS. v1's list had no bridge-gateway address (172.17.0.1 for docker0) and never passed
#      --add-host host.docker.internal:host-gateway, so the two routes a container can actually be
#      given were both unmeasured. v2 derives the container's own default-route gateway per leg and
#      adds a leg that injects the host alias, because the repo's own preflight REFUSES that alias
#      (scripts/feature_check.py:1056-1063) and only a measurement can say whether it was right to.
#
# TWO-SIDED, and the legend is corrected. v1's legend said "a target closed in BOTH is not a route".
# That was wrong, and v1's own output is the counterexample: a leg whose container really ran and
# whose client really answered `closed` is a MEASURED NEGATIVE, while a leg that died in the engine
# before starting is not a measurement at all. v1 could not tell them apart because it printed the
# engine's error text and the client's verdict in the same column. v2 classifies every row by
# whether a client verdict came back at all, so `closed` always means "asked, no answer" and never
# "could not ask". The listener is still raised twice -- 0.0.0.0 and 127.0.0.1 -- with everything
# else fixed, so a row open on 0.0.0.0 and closed on 127.0.0.1 is still the alias-routes-but-
# loopback-is-not-forwarded finding.
#
# It is a probe, not a real-tier run: one `--rm` container per test, no compose project, no volumes,
# nothing under any run root, no GPU container, and it needs neither agent-gpu nor the GPU. It binds
# its OWN free test port and refuses to start if that port is taken, so it cannot disturb a live
# stack (UR-133). Tear-down is the listener it started, and nothing else (UR-135). It mounts
# NOTHING, so an engine error on its stderr can carry only podman's own wrapper text and the target
# name being probed -- nothing private (this is the leak channel ruling 188 is about; the error tail
# is kept to the last 200 bytes for that reason).
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

# --- engines worth measuring -----------------------------------------------------
# A "leg" is one way the run could plausibly start its container. Legs are built from what THIS host
# offers, so a missing engine drops out with a reason instead of a false negative.
DOCKER_CMD=""; PODMAN_CMD=""
command -v docker >/dev/null 2>&1 && DOCKER_CMD=docker
command -v podman >/dev/null 2>&1 && PODMAN_CMD=podman
[[ -z "$DOCKER_CMD$PODMAN_CMD" ]] && { obs "neither docker nor podman on PATH -- nothing to measure"; exit 2; }

SOCK="/run/user/$(id -u)/podman/podman.sock"
SOCK_OK=""
if [[ -S "$SOCK" ]] && [[ -n "$DOCKER_CMD" ]] &&
   DOCKER_HOST="unix://$SOCK" docker version >/dev/null 2>&1; then
  SOCK_OK="$SOCK"      # this is the harness's route: moby CLI over podman's Docker-compatible socket
fi

note "engine"
obs "docker=${DOCKER_CMD:-<absent>} podman=${PODMAN_CMD:-<absent>}"
obs "DOCKER_HOST=${DOCKER_HOST:-<unset>}  uid=$(id -u)  XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-<unset>}"
if [[ -n "$SOCK_OK" ]]; then
  obs "harness route AVAILABLE: DOCKER_HOST=unix://$SOCK_OK (rootless podman's docker-compatible socket)"
  obs "server under that route=$(DOCKER_HOST="unix://$SOCK_OK" docker version --format '{{.Server.Version}}' 2>&1 | head -1)"
else
  obs "harness route NOT available: socket $SOCK $([[ -S "$SOCK" ]] && echo present || echo absent);"
  obs "if this host runs the stack through podman, enable it host-side with"
  obs "  systemctl --user enable --now podman.socket   (scripts/bootstrap-gb300.sh:112-127)"
fi
[[ -n "$PODMAN_CMD" ]] && obs "podman rootless=$(podman info --format '{{.Host.Security.Rootless}}' 2>/dev/null)"

# LEGS: label|client|DOCKER_HOST-value|extra-run-args. Order = most like the run first.
LEGS=()
if [[ -n "$SOCK_OK" ]]; then
  LEGS+=("harness-route|docker|unix://$SOCK_OK|")
  LEGS+=("harness-route+host-alias|docker|unix://$SOCK_OK|--add-host host.docker.internal:host-gateway")
fi
if [[ -n "$DOCKER_CMD" ]] && docker version >/dev/null 2>&1; then
  LEGS+=("docker-plain-default|docker||")
  LEGS+=("docker-plain+host-alias|docker||--add-host host.docker.internal:host-gateway")
fi
if [[ -n "$PODMAN_CMD" ]]; then
  LEGS+=("podman-default|podman||")
  LEGS+=("podman+host-alias|podman||--add-host host.docker.internal:host-gateway")
  LEGS+=("podman-slirp4netns|podman||--network slirp4netns:allow_host_loopback=true")
  LEGS+=("podman-pasta|podman||--network pasta")
fi
[[ ${#LEGS[@]} -eq 0 ]] && { obs "no engine answered -- nothing to measure"; exit 2; }

# --- one image per client's OWN store ----------------------------------------------
# v1's defect: an image from docker's store handed to podman dies before any connect.
images_of() { # $1 = client -> "repo:tag" lines from THAT client's store
  case "$1" in
    docker) DOCKER_HOST="${2:-}" docker images --format '{{.Repository}}:{{.Tag}}' 2>/dev/null ;;
    podman) podman images --format '{{.Repository}}:{{.Tag}}' 2>/dev/null ;;
  esac
}
resolve_image() { # $1 client, $2 DOCKER_HOST -> prefers a base image likely to hold a TCP client
  local c cand
  [[ -n "$IMG" ]] && { printf '%s' "$IMG"; return; }
  while IFS= read -r cand; do
    [[ -z "$cand" || "$cand" == *"<none>"* ]] && continue
    case "$cand" in
      *python*|*alpine*|*busybox*|*ubuntu*|*debian*|*node*) printf '%s' "$cand"; return ;;
    esac
  done < <(images_of "$1" "$2")
  while IFS= read -r cand; do               # no preferred name: first usable one
    [[ -z "$cand" || "$cand" == *"<none>"* ]] && continue
    printf '%s' "$cand"; return
  done < <(images_of "$1" "$2")
}

note "image per client store"
declare -A IMG_FOR
for cli in docker podman; do
  [[ "$cli" == docker && -z "$DOCKER_CMD" ]] && continue
  [[ "$cli" == podman && -z "$PODMAN_CMD" ]] && continue
  IMG_FOR["$cli"]="${IMG_FOR[$cli]:-$(resolve_image "$cli" "${SOCK_OK:+unix://$SOCK_OK}")}"
  obs "image[$cli store]=${IMG_FOR[$cli]:-<none found>}"
done
for cli in docker podman; do
  [[ "${IMG_FOR[$cli]:-}" == "$IMG" && -n "$IMG" ]] && obs "R195_PROBE_IMAGE pinned by you: used for every leg"
done
[[ -z "${IMG_FOR[docker]:-}${IMG_FOR[podman]:-}" ]] &&
  { obs "no local image to run a client from -- set R195_PROBE_IMAGE=<image:tag> present in BOTH stores"; exit 2; }

# A TCP connect is the whole measurement -- does that address:port answer. HTTP would add a second
# variable (which client the image carries, whether the server answers), so it is not used. Three
# client forms are tried in order and the one actually used is printed, so a verdict always names
# the thing that answered.
CLIENT_PROBE='
c=$1; pt=$2
if command -v python3 >/dev/null 2>&1; then used=python3
elif command -v nc >/dev/null 2>&1; then used=nc
elif command -v bash >/dev/null 2>&1; then used=bash
else echo "no-client"; exit 0; fi
# The nc/bash branches cannot separate an unresolvable name from a refused port either (nc -z
# exits 1 for both). Ask the resolver directly when the client cannot, so the verdict does not
# depend on which client the image happens to ship. Numeric targets need no resolver.
if [ "$used" != python3 ]; then
  case $c in
    *[!0-9.]*)
      if command -v getent >/dev/null 2>&1; then
        getent hosts "$c" >/dev/null 2>&1 || { echo "$used nodns"; exit 0; }
      fi ;;
  esac
fi
case $used in
# A bare connect() cannot tell "the name has no address here" from "it resolved and the port
# refused": both raise, and v1 printed `closed` for both. Read A proved the conflation bites -- on
# maui none of the three alias names resolve inside a plain bridge container, so the five closed
# docker rows in v1 were never measured negatives about routing. Resolve explicitly first: gaierror is
# reported as `nodns`, and `closed` now means a real connection attempt to a real address.
python3) r=$(python3 -c "import socket,sys
h,p=sys.argv[1],int(sys.argv[2])
try:
    socket.getaddrinfo(h,p)
except socket.gaierror:
    print(\"nodns\"); sys.exit(0)
s=socket.socket(); s.settimeout(4)
try:
    s.connect((h,p)); print(\"open\")
except Exception:
    print(\"closed\")" "$c" "$pt") ;;
nc)   if nc -z -w4 "$c" "$pt" 2>/dev/null; then r=open; else r=closed; fi ;;
bash) if bash -c "exec 3<>/dev/tcp/$c/$pt" 2>/dev/null; then r=open; else r=closed; fi ;;
esac
echo "$used $r"'

# The container's OWN default-route gateway: the address its rootless stack uses to reach the host.
# Read from /proc/net/route because `ip` and `netstat` are absent from most slim images. Column 2 is
# the destination (00000000 = default) and column 3 the gateway, each as 8 hex chars in REVERSED byte
# order, so 010011ac means 172.17.0.1. This code runs under the image's `sh`, so it is deliberately
# POSIX: awk+sed+cut+printf only -- no ${var:off:len} (a bashism busybox ash lacks) and no 16# base
# arithmetic (not portable). printf '%d' 0x.. is the portable hex-to-decimal step. The raw route line
# is printed too, so a reader can still name the gateway if the decode ever fails.
GATEWAY_PROBE='h=$(awk "\$2==\"00000000\"{print \$3; exit}" /proc/net/route 2>/dev/null)
printf "ROUTE %s\n" "$(tr "\n" ";" < /proc/net/route 2>/dev/null)"
if [ -z "$h" ]; then printf "GW ?\n"; exit 0; fi
o=$(printf "%s" "$h" | sed "s/\(..\)\(..\)\(..\)\(..\)/\4\3\2\1/")
printf "GW %d.%d.%d.%d\n" \
  "0x$(printf "%s" "$o" | cut -c1-2)" "0x$(printf "%s" "$o" | cut -c3-4)" \
  "0x$(printf "%s" "$o" | cut -c5-6)" "0x$(printf "%s" "$o" | cut -c7-8)"'

run_probe() { # $1 client, $2 DOCKER_HOST, $3 extra args, $4 image, $5 script, rest = argv
  local cli="$1" dh="$2" pre="$3" img="$4" sc="$5"; shift 5
  local out
  if [[ "$cli" == docker ]]; then
    out=$(DOCKER_HOST="$dh" docker run --rm $pre "$img" sh -c "$sc" sh "$@" 2>&1)
  else
    out=$("$cli" run --rm $pre "$img" sh -c "$sc" sh "$@" 2>&1)
  fi
  # A row whose container never started carries an engine error. Drop podman's timestamp/level/msg
  # wrapper and its random container id -- neither is a measurement -- and keep the TAIL, because the
  # reason follows "failed:". A head cut would keep the id and discard the reason.
  printf '%s' "$out" | tr '\n' '|' |
    sed -E 's/time=[^ ]+ level=[a-z]+ msg=//g; s/Preparing container [0-9a-f]+: //g' | tail -c 200
}

VERDICT_RE='^(python3|nc|bash) (open|closed|nodns)$'
declare -A ROW           # ROW[label|target|phase] = verdict text
declare -A GW            # GW[label] = gateway address for that leg
declare -A VALID         # VALID[label]=yes once the leg proved it can run the image at all

gw_of() { # $1 client, $2 dh, $3 pre, $4 img -> the container's default-route gateway, or <unknown>
  # The probe prints a labelled line; take only the GW value so a raw ROUTE line cannot leak into
  # the target list. A non-address result stays <unknown> rather than becoming a fake target.
  local g
  # run_probe folds newlines into '|', so '^GW ' would never match and every gateway would decode to
  # <unknown> -- silently dropping v2's whole point. Unfold the channel back to lines first.
  g=$(run_probe "$1" "$2" "$3" "$4" "$GATEWAY_PROBE" | tr '|' '\n' | sed -n 's/^GW //p' | head -1 | tr -d '[:space:]')
  [[ -z "$g" ]] && { printf '<unknown>'; return; }
  [[ "$g" =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]] && printf '%s' "$g" || printf '<unknown>'
}

BASE_TARGETS="host.docker.internal host.containers.internal gateway.docker.internal 10.0.2.2 127.0.0.1"

extra_target() { # $1 label -> the decoded gateway as a target, or nothing when it was undecodable
  local g="${GW[$1]:-}"
  [[ "$g" =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]] && printf ' %s' "$g"
}

sweep() { # $1 phase (control|test), $2 label, $3 client, $4 dh, $5 pre, $6 img
  local phase="$1" label="$2" cli="$3" dh="$4" pre="$5" img="$6" t targets
  # v2 regression caught by the mock run: v1 printed a heading per sweep, and without it the posted
  # output is an unattributed block of rows -- the reader cannot tell which leg or phase a row is.
  note "sweep $phase -- $label"
  targets="$BASE_TARGETS$(extra_target "$label")"
  local tseen=""; local -a tl=()
  for t in $targets; do [[ -z "$t" || "$tseen" == *" $t "* ]] && continue; tseen="$tseen $t "; tl+=("$t"); done
  for t in "${tl[@]}"; do
    local r; r=$(run_probe "$cli" "$dh" "$pre" "$img" "$CLIENT_PROBE" "$t" "$PORT")
    ROW["$label|$t|$phase"]="$r"
    printf '  %-26s %s\n' "$t" "${r:-<empty-output>}"
  done
}

# --- what the container can name at all, per leg -----------------------------------
for leg in "${LEGS[@]}"; do
  IFS='|' read -r label cli dh pre <<< "$leg"
  img="${IMG_FOR[$cli]:-}"
  note "leg $label (client=$cli${dh:+ DOCKER_HOST=$dh}${pre:+ $pre})"
  if [[ -z "$img" ]]; then obs "no image in the $cli store -- leg NOT-MEASURED"; continue; fi
  # The probe's own output channel folds newlines into '|' (see run_probe), so an anchored /^ok$/
  # would never match and every leg would be reported NOT-MEASURED -- a silent, total failure that
  # still exits 0. Match an unanchored marker token instead, which survives the folding.
  local_ok=$(run_probe "$cli" "$dh" "$pre" "$img" 'echo R195CANARY')
  if [[ "$local_ok" != *R195CANARY* ]]; then
    obs "this client cannot start the image -- leg NOT-MEASURED (reason tail: $local_ok)"
    continue
  fi
  VALID["$label"]=yes
  GW["$label"]=$(gw_of "$cli" "$dh" "$pre" "$img")
  obs "container's own default-route gateway: ${GW[$label]}"
  obs "names it can resolve -- $(run_probe "$cli" "$dh" "$pre" "$img" \
        'for n in host.containers.internal host.docker.internal gateway.docker.internal; do printf "%s=%s " "$n" "$(getent hosts $n | awk "{print \$1}" | head -1)"; done')"
  obs "no sweep here -- the listener is raised below, so every reach row is measured under both"
  obs "bind addresses. A sweep before the listener exists would print closed rows that mean nothing."
done

# --- the listener, twice -----------------------------------------------------------
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

# The finding needs the SAME rows under both bind addresses, so the sweep runs twice per leg and the
# summary pairs them. The first leg also runs a --network host control, which proves the listener and
# the client work at all: without it a whole sweep of `closed` could be a dead listener.
PHASE=""
CTL_LABEL=""   # the --network host positive control, recorded so the summary prints it too
run_phase() { # $1 bind, $2 phase
  PHASE="$2"
  # http.server's POSITIONAL argument is the PORT and --bind takes the ADDRESS. Getting these the
  # other way round makes the listener die on a bad port, and the listen_seen guard below then exits
  # 2 -- loudly, which is the only reason the mistake is survivable. Both phases must bind via
  # --bind or the 0.0.0.0 control and the 127.0.0.1 test are not two different conditions.
  python3 -m http.server "$PORT" --bind "$1" >/dev/null 2>&1 &
  LISTENER=$!
  sleep 1.5
  if ! listen_seen; then obs "listener on $1:$PORT never came up -- cannot conclude"; return 1; fi
  obs "listener ($2) as seen by the host: $(listen_line | tr -s ' ')"
  local first=1
  for leg in "${LEGS[@]}"; do
    IFS='|' read -r label cli dh pre <<< "$leg"
    # Sweep ONLY legs the validation loop proved runnable, so a dead leg never prints a fake closed.
    [[ "${VALID[$label]:-}" == "yes" ]] || continue
    if [[ $first -eq 1 ]]; then
      first=0
      CTL_LABEL="$label +nethost-CONTROL"
      CTL_CLI="$cli"; CTL_IMG="${IMG_FOR[$cli]}"
      sweep "$2" "$CTL_LABEL" "$cli" "$dh" "$pre --network host" "$CTL_IMG"
    fi
    sweep "$2" "$label" "$cli" "$dh" "$pre" "${IMG_FOR[$cli]}"
  done
  kill "$LISTENER" 2>/dev/null; LISTENER=""; sleep 0.5
  return 0
}

# Exit-code contract: a probe where EVERY leg failed validation measured nothing, and 0 would read
# as "measured, answer: no route" to anyone trusting the code instead of reading the table.
measurable=0
for leg in "${LEGS[@]}"; do
  IFS='|' read -r label _ <<< "$leg"
  [[ "${VALID[$label]:-}" == "yes" ]] && measurable=$((measurable+1))
done
if [[ $measurable -eq 0 ]]; then
  obs "0 of ${#LEGS[@]} legs could start a container -- NOTHING was measured. Fix a leg (see the"
  obs "NOT-MEASURED reasons above) and re-run; do not read the empty summary as 'no route'."
  exit 2
fi
obs "$measurable of ${#LEGS[@]} legs measurable"

note "CONTROL listener on 0.0.0.0 (every interface)"
run_phase 0.0.0.0 control || exit 2
note "UNDER TEST listener on 127.0.0.1 ONLY (what agent-gpu publishes)"
run_phase 127.0.0.1 test || exit 2

# --- summary -----------------------------------------------------------------------
emit_row() { # $1 label -- one leg (or the control) as summary rows, one per target
  local label="$1" t c u cm um reading
  for t in $BASE_TARGETS$(extra_target "$label"); do
    [[ -z "$t" ]] && continue
    c="${ROW["$label|$t|control"]:-}"; u="${ROW["$label|$t|test"]:-}"
    cm=closed; um=closed
    [[ "$c" =~ $VERDICT_RE ]] && cm="${c##* }" || cm=unmeasured
    [[ "$u" =~ $VERDICT_RE ]] && um="${u##* }" || um=unmeasured
    # Priority is instrument-first: an unmeasured side outranks any verdict, because a verdict from
    # a leg that never started is not a measurement. Then the answer, then the three kinds of no.
    if [[ "$cm" == unmeasured || "$um" == unmeasured ]]; then
      reading="NOT-MEASURED on at least one side"
    elif [[ "$um" == open ]]; then
      reading="REACHES a loopback-only listener"
    elif [[ "$um" == closed && "$cm" == open ]]; then
      reading="resolved+refused while the control was open: alias routes, host loopback not forwarded"
    elif [[ "$um" == nodns || "$cm" == nodns ]]; then
      reading="name does not resolve in this leg -- routing was never asked (see the resolution block)"
    else
      reading="resolved+refused on both listeners -- no route for this pair"
    fi
    printf '  %-32s %-26s %-8s %-8s %s\n' "$label" "$t" "$cm" "$um" "$reading"
  done
}

note "summary -- one row per leg and target; OPEN/CLOSED need a client verdict to count"
printf '  %-32s %-26s %-8s %-8s %s\n' LEG TARGET CONTROL "127ONLY" READING
# The positive control first: it is the row that licenses reading a closed/closed leg as "no route"
# rather than "dead listener". v1 swept it but never tabulated it, so a reader had to scroll back
# through two phases of unattributed rows to find the one result that makes the rest meaningful.
[[ -n "$CTL_LABEL" ]] && emit_row "$CTL_LABEL"
for leg in "${LEGS[@]}"; do
  IFS='|' read -r label cli dh pre <<< "$leg"
  [[ -z "${IMG_FOR[$cli]:-}" ]] && continue
  emit_row "$label"
done

note "how to read it"
obs "REACHES a loopback-only listener = the route box 2 asks to have measured and named, if the"
obs "leg is one the run could actually use (the harness route, or a network the run's compose renders)."
obs "resolved+refused while the control was open = the finding v1 expected: the name resolves and"
obs "reaches the host on a NON-loopback path, so agent-gpu would have to publish beyond loopback."
obs "nodns (shown in a column) = the name has no address inside that leg, so the probe never asked"
obs "the network anything. Read A showed all three alias names unresolvable in a plain bridge"
obs "container, so on maui this is the likely majority reading, and it is NOT a negative about routing."
obs "NOT-MEASURED = that leg could not ask (engine refused the image, or no client in it). It says"
obs "nothing about the route. This is the correction to v1's legend, which called every closed/closed"
obs "row not-a-route: a leg that ran and answered closed IS a measured negative, and v2 separates the"
obs "two by whether a client verdict came back rather than by the verdict's value."
obs "Choosing between the owner options (agent-gpu publishing beyond loopback, vs the container"
obs "sharing the host namespace) is not this probe's call."
exit 0
