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
#   0 - the Done-when is ESTABLISHED: nothing open, or all open ones closed
#       and re-verified (--plan: findings reported from a query that answered)
#   1 - a gh query failed — the front one (so "no answer" is never read as
#       "nothing open") or the post-close re-query (the loop did not finish).
#       Non-zero always means: the Done-when was NOT established.
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
      # Print the header comment block, not a line range. A hardcoded
      # 'sed -n 2,26p' is a line pin — the Blocker-1 fix grew the header and
      # would have silently cut the Exit Codes table out of --help (the same
      # ref-rot this package flags in 17-action-plan.md). A sed RANGE pattern
      # is worse: it re-arms on the header's closing '# ====' and prints the
      # whole script (measured). So: print the contiguous '#' block after the
      # shebang and stop at the first non-comment line.
      awk 'NR > 1 && /^#/ { print; next } NR > 1 { exit }' "$0"
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
#
# Command substitution, NOT a process substitution. `set -e` inspects the exit
# status of `$(…)` on an assignment line but never one inside `<(...)`, so the
# first draft — `mapfile -t OPEN < <(gh …)` — let a dead `gh` (bad repo, 401,
# rate limit) leave an EMPTY array, and empty is the same branch as "nothing
# open": exit 0 printing "Done-when satisfied" with a GraphQL error on stderr.
# Round-1 review (ops cell A) and the author reproduced that independently at
# 4cb551fb. "No answer" and "nothing open" are different worlds; only the ≥1
# leg could tell them apart, which is why the re-verification below — already a
# command substitution — never had the bug.
if ! OPEN_RAW=$(
  gh issue list --repo "$REPO" --state open --limit 200 --json number,title \
    --jq ".[] | select(.title | test(\"$TITLE_RE\")) | .number"
); then
  echo "ERROR: the open-issue query failed — cannot tell 'nothing open' from" \
       "'no answer'. Not closing anything; Done-when NOT satisfied." >&2
  exit 1
fi
mapfile -t OPEN < <(printf '%s' "$OPEN_RAW")

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
