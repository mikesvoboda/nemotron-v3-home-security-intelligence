#!/usr/bin/env bash
# r243 live-host render check — the PR-Done-when command owner ruling 243
# (Linear record 6222454848) requires: "PR shows rendering with/without
# ORCHESTRATOR_ENABLED=false on the runner's Compose". This is also the command
# docs/operator/deployment/README.md's [r162 -> r243] section points at.
#
# WHAT IT ANSWERS: does `backend` get the engine-socket mount in the state you
# are about to boot? ON (unset/`true`): mounted. OFF (`false` + the overlay
# `-f`): absent.
#
# WHY NOT A PLAIN GREP: a grep for podman.sock matches alloy's mount and the
# ORCHESTRATOR_* environment lines in BOTH states -- measured on the prod render,
# 6 hits ON and 4 hits OFF -- so the count cannot tell the states apart. This
# filter scopes to backend's OWN volumes sub-block, where the only match is the
# mount itself. Kept a text filter on purpose: it runs on every CLI this package
# is verified on, including podman-compose 1.6.0, which REJECTS `config
# --format json` ("unrecognized arguments") and so rules out a jq check.
#
# Required values come from the environment compose itself reads: `.env` in the
# project directory, or the shell. No secrets are duplicated here, and prod.yml's
# own `:?` guards stay the ones that complain -- this script only relays their
# message and fails, because a render that did not happen is NOT a socket-free
# render (the OFF leg would otherwise print a false "absent OK").
#
# Usage: scripts/r243-render-check.sh [compose-command]   (default: podman compose)
set -euo pipefail
cd "$(dirname "$0")/.."
read -r -a CLI <<< "${1:-${COMPOSE_CMD:-podman compose}}"

AWK='/^  backend:/{b=1;v=0;next}
     b&&/^  [A-Za-z0-9_-]+:$/{b=0;v=0}
     b&&/^    volumes:/{v=1;next}
     b&&v&&/^    [A-Za-z0-9_-]+:/{v=0}
     b&&v&&/\/var\/run\/podman\/podman\.sock/{print "MOUNTED"}'

status=0
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
for state in on off; do
  # Mirror setup_lib/deploy.py: the flag picks the marker file THROUGH prod.yml's
  # interpolated include, and the overlay `-f` is added only when the value is
  # exactly `false`. Any other spelling fails the include with "no such file" --
  # loud by design -- so this loop never boots an ambiguous shape.
  overlay=()
  [ "$state" = off ] && overlay=(-f docker-compose.engine-false.yml)
  flag=$([ "$state" = on ] && echo true || echo false)
  # `|| rc=$?` because `set -e` would otherwise abort on the failing render before
  # the code could be read, and the point of this script is to relay WHICH guard
  # complained rather than to die silently.
  rc=0
  ORCHESTRATOR_ENABLED="$flag" "${CLI[@]}" -p r243-render-check \
      -f docker-compose.prod.yml "${overlay[@]}" config \
      > "$tmp/$state.out" 2> "$tmp/$state.err" || rc=$?
  if [ "$rc" -ne 0 ]; then
    printf '%-3s  RENDER FAILED (rc=%s) -- nothing can be concluded:\n' "$state" "$rc"
    sed 's/^/      /' "$tmp/$state.err" | head -5
    status=1
    continue
  fi
  got=$(awk "$AWK" "$tmp/$state.out" | head -1)
  want=$([ "$state" = on ] && echo MOUNTED || echo "")
  if [ "$got" = "$want" ]; then
    printf '%-3s  backend socket mount: %-7s OK\n' "$state" "${got:-absent}"
  else
    printf '%-3s  backend socket mount: %-7s WRONG (expected %s)\n' \
      "$state" "${got:-absent}" "${want:-absent}"
    status=1
  fi
done
exit "$status"
