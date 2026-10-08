#!/usr/bin/env bash
# =============================================================================
# Close the open "Automated Rollback" incident issues (O1.9 box 5)
# =============================================================================
# .github/workflows/rollback.yml filed one issue per red Deploy run while
# Deploy was red on every push (D12), and rolled nothing back (no docker tag,
# no push, no redeploy anywhere in it). The owner ruled it deleted on
# 2026-10-08 (#6854 comment 6051919463): "A red Deploy run is the signal, and
# the daily batch reports it." #6875 deletes it and makes red mean red.
#
# O1.9's Done-when: "no 'Automated Rollback' issue is open." This script is
# that clause's executable form, run ONCE by the author after #6875 merges
# and Deploy reads green on the merge commit — closing them any earlier would
# close issues whose mechanism is still running.
#
# Usage:
#   ./scripts/close-rollback-issues.sh [--plan] [--link PR]
#
# Options:
#   --plan         List what would close; touch nothing (default if gh is
#                  unauthenticated — the guard test runs this mode)
#   --link PR      PR to cite in the closing comment (default: #6875)
#
# Exit Codes:
#   0 - nothing open, or all open ones closed (--plan: findings reported)
#   1 - gh call failed mid-run; the issues listed so far still stand
# =============================================================================

set -euo pipefail

REPO="${GH_REPO:-mikesvoboda/nemotron-v3-home-security-intelligence}"
LINK="#6875"
PLAN=0

while [ $# -gt 0 ]; do
  case "$1" in
    --plan) PLAN=1; shift ;;
    --link) LINK="$2"; shift 2 ;;
    --help | -h)
      sed -n '2,26p' "$0"
      exit 0
      ;;
    *)
      echo "unknown argument: $1 (try --help)" >&2
      exit 2
      ;;
  esac
done

TITLE_RE='Automated Rollback'

# Same query the package's evidence used, so the count here and in the PR body
# are the same measurement: open issues, newest first, title match.
mapfile -t OPEN < <(
  gh issue list --repo "$REPO" --state open --limit 200 --json number,title \
    --jq ".[] | select(.title | test(\"$TITLE_RE\")) | .number"
)

if [ ${#OPEN[@]} -eq 0 ]; then
  echo "0 open 'Automated Rollback' issues — Done-when satisfied, nothing to do."
  exit 0
fi

echo "${#OPEN[@]} open 'Automated Rollback' issue(s): ${OPEN[*]}"

if [ "$PLAN" = 1 ]; then
  echo "--plan: touching nothing. Re-run without --plan (author, after the"
  echo "merge commit's Deploy reads green) to comment-and-close each one."
  exit 0
fi

BODY="Closing: the workflow that filed this is deleted by ${LINK} (owner
ruling 2026-10-08: a red \`Deploy\` run is the signal, and the daily batch
reports it). The red this reported was the smoke test asserting a health
contract the CI stack cannot satisfy; ${LINK} states the real contract, so
after it a red Deploy means a real failure."

for n in "${OPEN[@]}"; do
  gh issue comment "$n" --repo "$REPO" --body "$BODY" >/dev/null
  gh issue close "$n" --repo "$REPO" >/dev/null
  echo "closed #$n"
done

# Verify the Done-when by re-running the measurement, not by trusting the loop.
REMAINING=$(gh issue list --repo "$REPO" --state open --limit 200 --json title \
  --jq "[.[] | select(.title | test(\"$TITLE_RE\"))] | length")
if [ "$REMAINING" != "0" ]; then
  echo "STILL OPEN: $REMAINING — the loop did not finish; re-run." >&2
  exit 1
fi
echo "Done-when verified: 0 open 'Automated Rollback' issues."
