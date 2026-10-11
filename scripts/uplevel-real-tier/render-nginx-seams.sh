#!/usr/bin/env bash
# Render frontend/nginx.conf through the entrypoint in a container and show what
# the seam markers did — the harness behind O1.11's "the default mode is unchanged".
#
# Why this exists: O1.11's strongest Done-when clause is that the UNEXPOSED render is
# unchanged. Not behaviorally unchanged — BYTE unchanged. That is only observable by
# rendering, so the seam is a bare marker line that `sed … /d` deletes whole in default
# mode (each marker occupies a blank line the file already had). Comparing two renders
# is the whole test, and it must be re-runnable by a reviewer, so it lives here rather
# than in someone's shell history (contract rule 3).
#
# It runs nginx -t on every render: the harness that caught the one bug a unit test
# could not see (an unfinalized __HSI_AUTH_ANCHOR__ survived into a render and nginx
# refused to parse its own config).
#
# Nothing is published, nothing is started as a service, no stack is touched: `--rm`,
# `--entrypoint /bin/sh`, and `nginx -t` (validate and exit). The render is read from
# the container's own conf.d, which UID 101 can write; it comes back on stdout between
# sentinels because a bind mount would be owned by whoever created it.
#
# Usage (from a checkout root):
#   scripts/uplevel-real-tier/render-nginx-seams.sh                 # all four modes, diffed
#   scripts/uplevel-real-tier/render-nginx-seams.sh --dump ssl-exposed
#   scripts/uplevel-real-tier/render-nginx-seams.sh --entrypoint /tmp/base.sh --base
#
# --base compares against a SECOND entrypoint (pass it with --entrypoint): the
# byte-identity claim is a diff against the pre-O1.11 entrypoint, so run it once with
# HEAD's copy and once with the current one and diff the dumps.
set -euo pipefail

IMAGE="${NGINX_RENDER_IMAGE:-docker.io/nginxinc/nginx-unprivileged:stable-alpine-slim}"
# A throwaway render value, not a real credential: the exposed branch substitutes whatever
# MONITORING_API_KEY holds, and the harness only asserts the value lands in the render.
TEST_KEY="hsi_RENDERPROBE0" # pragma: allowlist secret
CONF="${CONF:-frontend/nginx.conf}"
ENTRYPOINT="${ENTRYPOINT:-frontend/docker-entrypoint.sh}"
CERT_DIR="${CERT_DIR:-}"
MODE=""
BASE=0

while [ $# -gt 0 ]; do
  case "$1" in
    --dump) MODE="${2:?mode: plain-default|plain-exposed|ssl-default|ssl-exposed}"; shift 2 ;;
    --base) BASE=1; shift ;;
    --entrypoint) ENTRYPOINT="${2:?path to a docker-entrypoint.sh}"; shift 2 ;;
    --conf) CONF="${2:?path to nginx.conf}"; shift 2 ;;
    -h|--help) sed -n '2,30p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

# SSL branches need a cert at /etc/nginx/certs; the entrypoint skips the ssl server
# block when none is present, so a missing dir silently tests the wrong branch.
CERT_MADE_US=0
cleanup_cert_dir() { [ "$CERT_MADE_US" = 1 ] && rm -rf "$CERT_DIR"; true; }
trap cleanup_cert_dir EXIT
ensure_certs() {
  if [ -z "$CERT_DIR" ]; then
    CERT_DIR="$(mktemp -d)"; CERT_MADE_US=1
    openssl req -x509 -newkey rsa:2048 -nodes -keyout "$CERT_DIR/key.pem" \
      -out "$CERT_DIR/cert.pem" -days 1 -subj "/CN=render-probe" >/dev/null 2>&1
    # mktemp -d is mode 700 and the key lands 600: the container's UID 101 could not
    # traverse the dir or read the key, and the entrypoint — correctly — treats an
    # unreadable cert as "no SSL" and skips the ssl server block, silently rendering
    # the WRONG branch. A one-day self-signed probe key is worthless by construction,
    # so make the throwaway material world-readable instead of pretending it failed.
    chmod 755 "$CERT_DIR"; chmod 644 "$CERT_DIR/cert.pem" "$CERT_DIR/key.pem"
  fi
  # Loud guard, same trap: refuse to run an ssl mode whose cert the container can't see.
  if [ ! -r "$CERT_DIR/cert.pem" ] || [ ! -r "$CERT_DIR/key.pem" ]; then
    echo "FATAL: $CERT_DIR has no readable cert.pem/key.pem — an ssl mode would silently render the non-ssl branch" >&2
    exit 1
  fi
}

# $1 = mode. Prints the validated render on stdout; diagnostics on stderr.
render() {
  local mode="$1" env_args=() cert_args=()
  case "$mode" in
    plain-default) ;;
    plain-exposed) env_args=(-e EXPOSE_LAN=yes -e "MONITORING_API_KEY=$TEST_KEY") ;;
    ssl-default) env_args=(-e SSL_ENABLED=true); ensure_certs; cert_args=(-v "$CERT_DIR:/etc/nginx/certs:ro") ;;
    ssl-exposed) env_args=(-e SSL_ENABLED=true -e EXPOSE_LAN=yes -e "MONITORING_API_KEY=$TEST_KEY"); ensure_certs; cert_args=(-v "$CERT_DIR:/etc/nginx/certs:ro") ;;
    *) echo "unknown mode: $mode" >&2; return 2 ;;
  esac
  # Accept either a repo-relative path (the default) or an absolute one (a reviewer's
  # `git show origin/main:frontend/docker-entrypoint.sh > /tmp/base.sh` copy).
  local conf="$CONF" ep="$ENTRYPOINT"
  [ "${conf:0:1}" = "/" ] || conf="$PWD/$conf"
  [ "${ep:0:1}" = "/" ] || ep="$PWD/$ep"
  docker run --rm "${env_args[@]}" "${cert_args[@]}" \
    -v "$conf:/src/nginx.conf:ro" \
    -v "$ep:/entrypoint.sh:ro" \
    --entrypoint /bin/sh "$IMAGE" \
    -c 'cp /src/nginx.conf /etc/nginx/conf.d/default.conf
        sh /entrypoint.sh nginx -t >/tmp/t.log 2>&1 || { echo RENDER-NGINX-T-FAILED >&2; cat /tmp/t.log >&2; exit 1; }
        grep -iE "emerg" /tmp/t.log >&2 && exit 1
        echo "===BEGIN==="; cat /etc/nginx/conf.d/default.conf; echo "===END==="' \
    | sed -n '/^===BEGIN===$/,/^===END===$/p' | sed '1d;$d'
}

if [ -n "$MODE" ]; then
  render "$MODE"
  exit $?
fi

# Default: render all four, assert the two default-mode renders carry no seam residue,
# and report the exposed mode's evidence counts.
fails=0
mkdir -p "${RENDER_OUT_DIR:-/tmp}"
for mode in plain-default plain-exposed ssl-default ssl-exposed; do
  # Deterministic name so two runs (HEAD's entrypoint vs the current one) can be diffed.
  out="${RENDER_OUT_DIR:-/tmp}/hsi-render-$mode.conf"
  render "$mode" > "$out" || { echo "FAIL: $mode did not render (nginx -t)"; fails=$((fails+1)); continue; }
  lines=$(wc -l < "$out")
  case "$mode" in
    *default)
      residue=$(grep -c '__HSI\|_hsi_auth\|hsi-grafana-auth\|listen 8081' "$out" || true)
      printf '%-14s %5s lines  seam-residue=%s %s\n' "$mode" "$lines" "$residue" \
        "$([ "$residue" = 0 ] && echo OK || { echo "<- MUST BE 0"; fails=$((fails+1)); })"
      ;;
    *)
      printf '%-14s %5s lines  includes=%s auth-endpoints=%s machine-listener=%s key-injected=%s\n' \
        "$mode" "$lines" \
        "$(grep -c 'include /tmp/hsi-grafana-auth.conf;' "$out" || true)" \
        "$(grep -c 'location = /_hsi_auth {' "$out" || true)" \
        "$(grep -c 'listen 8081;' "$out" || true)" \
        "$(grep -c "X-API-Key \"$TEST_KEY\"" "$out" || true)"
      ;;
  esac
  if [ "$BASE" = 1 ]; then
    echo "kept: $out"
  else
    rm -f "$out"
  fi
done

if [ "$fails" -gt 0 ]; then
  echo "FAILED: $fails mode(s) did not pass" >&2
  exit 1
fi
echo "all four modes render under nginx -t; default modes carry no seam residue"
